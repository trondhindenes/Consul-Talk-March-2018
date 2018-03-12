service nginx start
consul agent \
    -bind=0.0.0.0 \
    -retry-join=consul-0.consul.${NAMESPACE}.svc.cluster.local \
    -domain=cluster.local \
    -data-dir=/consul/data \
    -config-dir=/consul/config