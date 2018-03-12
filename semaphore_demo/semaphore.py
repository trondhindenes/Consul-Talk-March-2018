from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import datetime
import json
import logging
import os
import socket
import time

import consul

_log = logging.getLogger(__name__)


class Semaphore(object):
    """
    A distributed semaphore using the Consul Key/Value store.

    This is useful when you want to coordinate many services while
    restricting access to certain resources.

    Example of allowing only five processes to access the Foo Service
    from a cluster of many nodes and processes.
    >> with Semaphore('my_foo_service', 5):
    >>     do_the_foo()

    Based on https://www.consul.io/docs/guides/semaphore.html
    Their guide is a little rough so here's my best attempt at explaining what's going on.
    Consul doesn't have a semaphore out of the box, but what it does have
    is session based locking on its key/value store. And it knows how to do
    all the hard work of storing values in a HA cluster without race conditions.
    It can also expire sessions based on health checks such as a server going offline.

    Steps of acquiring a slot in the semaphore:
    1. Create a health check that ensures the current pid is running every second.
        This bit isn't covered in their guide. We add this so multiple processes
        on the same server (node) can compete for slots and Consul will expire
        sessions if the pid goes away instead of waiting until the whole node goes
        offline, which is the default.

    2. Create a session. In Consul, sessions act as a binding layer between
        nodes, health checks, and key/value data.
        https://www.consul.io/docs/internals/sessions.html
        The returned ID for this new session is what will be
        stored in the semaphore slots to denote how many slots are currently
        spoken for.

    3. Create a contender entry. This is nothing more than a dummy entry in the
        key/value store. Its key includes the session ID to avoid collisions
        and the value can be used by humans for debugging if needed. The real
        point to this is that it is created using the `acquire` param. This
        puts a "lock" on the contender entry. In Consul speak that just means
        that if you query the key the result includes the session ID that has a
        "lock", as long as that session is still active. One thing to note
        about Consul is that the presence of a "lock" does not mean others
        can't act on the key, as their docs put it:
            "Any client can read, write, and delete a key without owning
             the corresponding lock. It is not the goal of Consul to
             protect against misbehaving clients."
        This entry will be automatically deleted when the session becomes
        inactive because of the behavior declared on the session.

    4. Do a recursive query against all key/values under the namespace
        of `service/{service_name}/lock/`. This will return us a list
        of values where each can be grouped into one of three buckets:
         a. 0 or 1 entry for the lock record which holds the source of truth
            on which session IDs currently have slots in the semaphore.
            Its key will be in the form of `service/{service_name}/lock/.lock`.
         b. 0 or more contender entries with an active session.
         c. 0 or more contender entries without an active session.

    5. Delete the contender entries that no longer have an active session.
        This is a bit of house cleaning so the key store doesn't get
        bloated as processes fail without properly releasing their own locks.
        This step should never really execute in the loop as the
        sessions use the `delete` behavior and these entries are
        created already acquired by the session.

    6. Compare the concurrency limit provided to the one in the lock record.
        This mechanic is suggested to ensure that all the processes are working
        under the same assumptions when negotiating. Depending on our needs,
        we may or may not want to raise an error here.

    7. Get the intersection of the active session IDs from the contender entries
        and the session IDs in the lock record. This should be the list of all the
        sessions that are still working away with a valid slot in the semaphore.

    8. Compare the concurrency limit to the number of valid sessions.
        If the semaphore is currently full we can either raise an exception
        or loop back to step 4 and wait until a slot opens up, depending on
        whether we're blocking or not.

    9. Attempt to update the lock record with the list of valid sessions plus
        our own session ID. As far as the current process is concerned this
        is what the slots should look like given the info we have.
        The magic to avoid a race condition comes from the use of the
        `cas` (Check-And-Set) param, which ensures that only one process
        can update the lock record at a time using an integer we received
        during the recursive query.
        If the record is successfully updated then the lock is acquired.
        If not we loop back to step 4, get the new state of the semaphore
        and try again from there.

    """

    def __init__(self, service_name, concurrency_limit, host_url='localhost:8500'):
        consul_port = host_url.split(':')[1]
        consul_host = host_url.split(':')[0]
        self.client = consul.Consul(host=consul_host, port=consul_port)
        self.concurrency_limit = concurrency_limit
        self.local_node_name = self.client.agent.self()['Member']['Name']
        self.prefix = 'service/{}/lock/'.format(service_name)
        self.session_id = None
        self._acquired = False

    @property
    def acquired(self):
        return self._acquired

    def acquire(self, block=True):
        if self._acquired:
            raise RuntimeError("Already acquired.")

        # Create a session and add a contender entry.
        self._clear_session()
        #pid_health_check_id = self._pid_health_check()
        self.session_id = self.client.session.create(
            name='semaphore',
            behavior='delete',  # allows the contender entry to auto delete
            ttl=3600,  # this ttl is a last resort, hence its length
        )
        _log.debug("Created session: %s.", self.session_id)

        contender_key = '{}{}'.format(self.prefix, self.session_id)
        contender_value = json.dumps({
            # The contents of this dict are opaque to Consul and
            # not used for the locking mechanism at all.
            # It's provided in the hope that it may help humans.
            'time': datetime.datetime.utcnow().isoformat(),
            'host': socket.gethostname(),
            'pid': os.getpid(),
        })
        if not self.client.kv.put(contender_key, contender_value, acquire=self.session_id):
            raise RuntimeError("Failed to add contender entry.")
        _log.debug("Created contender entry.")

        # loop until we successfully get our session saved into a slot.
        prefix_index = 0
        lock_key = '{}.lock'.format(self.prefix)

        while True:
            # The first time around the index is set to zero which
            # means it will return right away (non-blocking).
            # In the case we loop around because PUTing the new lock
            # info failed, it can be assumed the index of the prefix
            # has changed so the next call to kv.get will not block either.
            # In the case that we loop around and try again because all
            # the slots are full, this call will block until the
            # index on the prefix hierarchy is modified by another process.
            _log.debug("Getting state of semaphore. Index: %s.", prefix_index)
            prefix_index, pv = self.client.kv.get(self.prefix, index=prefix_index, recurse=True)
            _log.debug("Current index of semaphore: %s.", prefix_index)

            lock_modify_index = 0
            current_lock_data = {}
            active_sessions = set()

            for entry_value in pv:
                if entry_value['Key'] == lock_key:
                    lock_modify_index = entry_value['ModifyIndex']
                    current_lock_data = json.loads(entry_value['Value'])
                    continue

                if entry_value.get('Session'):
                    active_sessions.add(entry_value['Session'])
                    continue

                # Delete any contender entries without an active session.
                _log.debug("Deleting dead contender: %s.", entry_value['Key'])
                self.client.kv.delete(entry_value['Key'])

            sessions_in_slots = set(current_lock_data.get('holders', []))
            limit = int(current_lock_data.get('limit', self.concurrency_limit))

            if limit != self.concurrency_limit:
                _log.debug("Limit mismatch. Remote %s, Local %s.", limit, self.concurrency_limit)
                # Take the provided limit as the truth as a config may
                # have changed since the last process updated the lock.
                limit = self.concurrency_limit

            valid_sessions = active_sessions & sessions_in_slots

            if len(valid_sessions) >= limit:
                _log.debug("All slots are full. %s of %s.", len(valid_sessions), limit)
                if not block:
                    raise RuntimeError("Unable to acquire lock without blocking.")
                continue  # try again

            # Add our session to the slots and try to update the lock.
            valid_sessions.add(self.session_id)
            new_lock_value = json.dumps({
                'limit': limit,
                'holders': list(valid_sessions),
            })

            # This will not update and will return `False` if the index is out of date.
            self._acquired = self.client.kv.put(lock_key, new_lock_value, cas=lock_modify_index)
            _log.debug("Lock update attempt %s.", 'succeeded' if self._acquired else 'failed')
            if self._acquired:
                break  # yay

    def release(self):
        if not self._acquired:
            raise RuntimeError("Not acquired.")
        self._clear_session()
        self._acquired = False

    def _clear_session(self):
        if self.session_id:
            # Docs recommend updating the .lock to remove session from slot.
            # Seems like an unneeded round-trip. going to skip for now.
            _log.debug("Removing health check and session.")
            self.client.session.destroy(self.session_id)
            self.client.agent.check.deregister('pidHealth:{}'.format(os.getpid()))
            self.session_id = None

    def _pid_health_check(self):
        """
        Ensure a registered and passing check is running for this pid.

        Does not create the check if it already exists and blocks until
        the check is passing.

        During `_clear_session` the health check is manually destroyed.
        If the process can't clean up then the check sticks around on
        the node in a critical state for 72 hours (configurable on the
        cluster) before being garbage collected.

        Note: the use of `client.health.check` is used here instead
        of `client.agent.checks` because it's possible for the local
        node to show a 'passing' status on the new health check before
        the servers in the cluster, and in order for a session to be
        created the servers must agree that the new check is 'passing'.

        :return str: the ID of the check
        """
        pid_check_id = 'pidHealth:{}'.format(os.getpid())
        index, checks = self.client.health.node(self.local_node_name)

        if not any(check['CheckID'] == pid_check_id for check in checks):
            _log.debug("Registering pid health check. PID %s.", pid_check_id)
            registered = self.client.agent.check.register(
                name="Semaphore PID",
                check_id=pid_check_id,
                check={
                    # Uses `ps` to check if this pid is still running, normally
                    # a missing pid will have an exit code of `1`, but that
                    # will only cause the check to enter a warning state and
                    # we need it to enter a critical state to have effect,
                    # hence the `exit 2`.
                    'script': 'ps -p {} || exit 2'.format(os.getpid()),
                    'interval': '1s',
                    'timeout': '1s',
                },
            )
            if not registered:
                raise RuntimeError("Unable to register health check.")

        start = time.time()
        while True:
            check = next((check for check in checks if check['CheckID'] == pid_check_id), None)

            if check and check['Status'] == 'passing':
                break

            if time.time() - start > 5:
                raise RuntimeError("PID health check refuses to pass.")

            index, checks = self.client.health.node(self.local_node_name, index=index, wait='5s')

        return pid_check_id

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        del exc_type, exc_val, exc_tb
        try:
            self.release()
        except RuntimeError:
            pass