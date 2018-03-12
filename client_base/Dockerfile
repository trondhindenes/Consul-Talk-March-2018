FROM ubuntu
WORKDIR /consul
RUN \
    apt-get update &&\
    apt-get install -y wget unzip &&\
    rm -rf /var/lib/apt/lists/*
RUN \
    wget https://releases.hashicorp.com/consul/1.0.6/consul_1.0.6_linux_amd64.zip
RUN \
    unzip consul_1.0.6_linux_amd64.zip &&\
    cp consul /usr/local/bin/consul &&\
    mkdir /consul/data
ENTRYPOINT ["consul"]

