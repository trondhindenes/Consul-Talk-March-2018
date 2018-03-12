FROM consul_client_base:1.0.0
WORKDIR /consul
RUN \
    apt-get update &&\
    apt-get install -y nginx &&\
    rm -rf /var/lib/apt/lists/*
WORKDIR /bootstrap
COPY bootstrapper.sh .
ENTRYPOINT ["/bin/bash"]
CMD ["-c", "/bootstrap/bootstrapper.sh"]

