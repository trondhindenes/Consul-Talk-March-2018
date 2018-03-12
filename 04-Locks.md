# 04-Locks

WARNING: Advanced stuff!!


Consul can act as a _semaphore_ where several _condenders_ attempt to "lock" a given key. This can be used for coordinating activites across distributed systems.

In order to run this, you need to communicate "thru" two separate agents to simulate multiple clients. Using kubectl we can map the same port on two different pods to two different local ports so that we can experiment with locks:

First, scale the nginx deployment to two pods:   

`kubectl scale deployment consul-client-nginx --replicas 2`

Then, perform a port-forward to both of them on different ports (we're using 9000 and 9001 here:)
`kubectl port-forward <first pod> 9000:8500`
`kubectl port-forward <second pod> 9001:8500`

In two separate console windows we can now run (make sure you have the necessary requirements first, you'll find then in the requirements file in the semaphore_demo directory):

```bash
cd semaphore_demo
python3 \
    get_lock.py \
    --endpoint-url localhost:9000 \
    --lock-path mytestservice \
    --log-level debug
```

```bash
cd semaphore_demo
python3 \
    get_lock.py \
    --endpoint-url localhost:9001 \
    --lock-path mytestservice \
    --log-level debug
```

You should see that the lock is passed back and forth between the two agents. Consul-Ping-Pong!!


