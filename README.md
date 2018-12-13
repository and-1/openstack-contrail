Provisioning and deploy openstack with contrail network component
1. Install jump server
  a. Install OS 18.04 on one server
  b. Configure one network interface for ansible (example netplan config in bond_netplan.example)
  c. Configure maas.ini inventory file
  d. Deploy maas server to jump server (deploy_maas.yaml)
2. Login on maas server and pass postinstall wizard
3. Rum BM server with enabled PXE
4. Add appear servers to appropriate zone in maas

