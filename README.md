## Provisioning and deploy openstack with contrail network component

## Description of inventory dir
Some shell output was omitted
```bash
inventory # Inventory dir contain different files grouped by region
├── regionOne # OS region name 
│   ├── artifacts # Dir contain downlonded or generated from tempalte files
│   │   ├── admin.conf # KUBECONFIG file for connect to deployed kubernetes cluster
│   │   ├── cloud.yaml # Admin credentials for connect to deployed Openstack
│   │   ├── helm_vars_ceph-mon.yaml # Generated files for override default helm charts values
│   │   ├── helm_vars_ceph-openstack-config.yaml
│   │   └── kubectl # Dowloaded binary file for manage kubernetes cluster
│   ├── credentials # Dir contain sensitive data like passwords and tokens. !!!DON'T DELETE THIS FILES!!!
│   │   ├── ceph_object_store.elasticsearch.secret_key.creds
│   │   ├── contrail_endpoints.rabbitmq.creds
│   │   ├── maas.ui.creds
│   │   ├── nagios.admin.creds
│   │   ├── oslo_db.admin.creds
│   │   └── prometheus_mysql_exporter.user.creds
│   ├── group_vars # Default ansible location for variables
│   │   ├── all # Variables for all ansible host groups
│   │   │   ├── all.yml
│   │   │   ├── docker.yml
│   │   │   └── osh.yml # The main config file for roles in this repo
│   │   ├── etcd.yml
│   │   └── k8s-cluster # Variables for k8s-cluster ansible groups
│   │       ├── addons.yml
│   │       ├── k8s-cluster.yml
│   │       └── k8s-net-calico.yml
│   ├── helm_vars # Suppementary vars dir. Files are included to role using include_vars 
│   │   ├── components.yaml # File contain components which must be deployed
│   │   ├── endpoints.yaml # File contain different endpoints of components. Such as username, password, fqdn
│   │   ├── images.yaml # What images will be used
│   │   └── replicas.yaml # How many replicas will be used
│   ├── hosts.yaml.sample # Example of static inventory file for deploy openstack-contrail
│   ├── inventory.py # Dymanic inventory file. Is gets info from MAAS
│   └── maas.ini # Inventory file for deploy MAAS
└── share_creds # Dir contain some sensitive data required for use generated info through different
    │           # role and deployment
    ├── ceph.regionone.creds
    ├── identity.admin.creds
    ├── maas.region.endpoint
    └── maas.ssh.key.pub
```

## Install
1. Install jump server
  - Install Ubuntu 18.04 on one server/vm
  - Configure one network interface for ansible (example netplan config in bond_netplan.example)
  - Configure maas.ini inventory file
  - Deploy maas server to jump server (deploy_maas.yaml)
```bash
ansible-playbook -i path_to_inventory deploy_maas.yaml
```

2. Login on maas server and pass postinstall wizard
3. Rum BM server with enabled PXE
4. Add appear servers to appropriate zone in maas

