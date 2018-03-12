# 02-Add-A-Client

Once our cluster is set up, it's time to spin up a client (non-server) to join the cluster:

```bash
#Build the base docker image
cd client_base
./buildit.sh

cd ..
cd client_base_manifest
kubectl apply -f .
cd ..
```

This brings up a "bare" client without any services or anything, it will simply join the cluster and sit there. You can use this for connectivity testing while restarting a server pod.

More exiting is to bring up a client that will register a _service_ with Consul. Let's bring up a container running both Nginx and Consul:

```bash
#Build the nginx docker image
cd client_nginx
./buildit.sh

cd ..
cd client_nginx_manifest
kubectl apply -f .
cd ..
```

After a few seconds, the service `nginx` should register. Watch what happens if you exec into the pod and stop the nginx service:   
`kubectl exec <pod-name> /bin/bash -it`   

`service nginx stop`

`service nginx start`