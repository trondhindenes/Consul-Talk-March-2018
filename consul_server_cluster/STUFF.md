
kubectl create configmap consul --from-file=configs/server.json
kubectl create -f services/consul.yaml
kubectl create -f statefulsets/consul.yaml