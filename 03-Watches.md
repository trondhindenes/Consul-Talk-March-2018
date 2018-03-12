# 03-Watches

Any Consul agent can "watch" for changes in a service or a KV path.
You can test this using the `client_watcher_manifest` directory:

```bash
cd client_watcher_manifest
kubectl apply -f .
cd ..
```

This adds another consul agent which doesn't do anything except watch for changes in the nginx service. Stream this pod's output while scaling up/down the nginx deployment!

Consul can also watch for changes in the KV store:

```bash
cd client_kvwatcher_manifest
kubectl apply -f .
cd ..
```

Watch this pod's output while changing the value of the `foo/bar/baz` KV key.