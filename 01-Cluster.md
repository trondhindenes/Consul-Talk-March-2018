# 01-Cluster

Bootstrap the cluster by doing the following from the `consul_server_cluster` dir:   
`kubectl create configmap consul --from-file=configs/server.json`   
`kubectl create -f services/consul.yaml`   
`kubectl create -f statefulsets/consul.yaml`   

This creates a 3-node statefulset
Verify by outputting the logs from one of the pods:   
`kubectl logs -f consul-0`

You can also browse the Consul UI, which will be available on the servers:   
`kubectl port-forward consul-0 8500:8500`   
...and then open `http://localhost:8500` in your browser. It's a good idea to have the this connection open in a separate console window while you experiment with Consul, so you can visit the UI at all times.

At this point the cluster has quorum and will handle the loss of a single pod. You can test it by running:   
`kubectl delete pod consul-2`

WARNING: Do NOT use this configuration in production! It is insecure and does _not_ persist data directories properly!!