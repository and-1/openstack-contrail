#!/usr/bin/env python

"""
Ansible Dynamic Inventory Script for Ubuntu MAAS.
This script fetches hosts data for Ansible from Ubuntu MAAS, using Tags to
identify groups and roles. It is expected that the script will be copied to
Tower within the new Inventory Scripts dialog offered within the interface,
where it will be passed the `--list` argument to invoke the dynamic inventory
process.
It is also possible to run as a standalone script or a replacement for the
Ansible `hosts` file.
See https://docs.ubuntu.com/maas/2.1/en/api for API details
:copyright: Internet Solutions (Pty) Ltd, 2015
:author: Paul Stevens <mailto:paul.stevens@is.co.za>
:copyright: Martijn van der kleijn, 2017
:author: Martijn van der Kleijn <mailto:martijn.niji@gmail.com>
:license: Released under the Apache 2.0 License. See LICENSE for details.
:version: 2.0.1
:date: 11 May 2017
"""

import argparse
import json
import os
import re
import sys
import uuid
import pickle

import oauth.oauth as oauth
import requests
import ipaddress
import yaml

class Config:
  maas_api_url_file = "../share_creds/maas.region.endpoint"
  maas_api_key_file = "../share_creds/maas.apikey.creds"
  osh_ansible_env = "group_vars/all/osh.yml"
  min_compute_nodes = 3
  min_control_nodes = 1
  with open(os.path.join(os.path.dirname(__file__), osh_ansible_env),'r') as file:
    osh_config = yaml.safe_load(file)
  min_osd_nodes = osh_config['replication']
  

class Inventory:
    """Provide several convenience methods to retrieve information from MAAS API."""

    def __init__(self):
        """Check for precense of mandatory environment variables and route commands."""
        self.supported = '2.0'
        self.apikeydocs = 'https://docs.ubuntu.com/maas/2.1/en/manage-cli#log-in-(required)'

        self.maas = os.environ.get("MAAS_API_URL", None)
        if not self.maas:
            with open(os.path.join(os.path.dirname(__file__), Config.maas_api_url_file),'r') as f:
              self.maas = "{}api/2.0/".format(f.read()).decode('utf-8')
            if not self.maas:
              sys.exit("MAAS_API_URL environment variable not found. Set this to http<s>://<HOSTNAME or IP>/MAAS/api/{}".format(self.supported))
        self.token = os.environ.get("MAAS_API_KEY", None)
        if not self.token:
            with open(os.path.join(os.path.dirname(__file__), Config.maas_api_key_file),'r') as f:
              self.token = f.read().decode('utf-8')
            if not self.token:
              sys.exit("MAAS_API_KEY environment variable not found. See {} for getting a MAAS API KEY".format(self.apikeydocs))
        self.args = None

        # Parse command line arguments
        self.cli_handler()

        if self.args.list:
            self.checker()
            print json.dumps(self.inventory(), sort_keys=True, indent=2)
        elif self.args.host:
            print json.dumps(self.host(), sort_keys=True, indent=2)
        elif self.args.nodes:
            print json.dumps(self.nodes(), sort_keys=True, indent=2)
        elif self.args.tags:
            print json.dumps(self.tags(), sort_keys=True, indent=2)
        elif self.args.tag:
            print json.dumps(self.tag(), sort_keys=True, indent=2)
        elif self.args.supported:
            print self.supported()
        else:
            sys.exit(1)

    def supported(self):
        """Display MAAS API version supported by this tool."""
        return self.supported

    def auth(self):
        """Split the user's API key from MAAS into its component parts (Maas UI > Account > MAAS Keys)."""
        (consumer_key, key, secret) = self.token.split(':')
        # Format an OAuth header
        resource_token_string = "oauth_token_secret={}&oauth_token={}".format(secret, key)
        resource_token = oauth.OAuthToken.from_string(resource_token_string)
        consumer_token = oauth.OAuthConsumer(consumer_key, "")
        oauth_request = oauth.OAuthRequest.from_consumer_and_token(
            consumer_token, token=resource_token, http_url=self.maas,
            parameters={'auth_nonce': uuid.uuid4().get_hex()})
        oauth_request.sign_request(
            oauth.OAuthSignatureMethod_PLAINTEXT(), consumer_token, resource_token)
        headers = oauth_request.to_header()
        headers['Accept'] = 'application/json'
        return headers

    def host(self):
        """Return data on a single host/node."""
        host = {}
        headers = self.auth()

        url = "{}/nodes/{}/".format(self.maas.rstrip(), self.args.host)
        request = requests.get(url, headers=headers)
        return json.loads(request.text)

    def tags(self):
        """Fetch a simple list of available tags from MAAS."""
        headers = self.auth()

        url = "{}/tags/".format(self.maas.rstrip())
        request = requests.get(url, headers=headers)
        response = json.loads(request.text)
        tag_list = [item["name"] for item in response]
        return tag_list

    def tag(self):
        """Fetch detailed information on a particular tag from MAAS."""
        headers = self.auth()

        url = "{}/tags/{}/?op=machines".format(self.maas.rstrip(), self.args.tag)
        request = requests.get(url, headers=headers)
        return json.loads(request.text)
 
    def checker(self):
        """Check some segnificant parameters"""
        res = {'counts':{'control-plane':0,'compute-plane':0,'osd-nodes':0}}
        for tag in res['counts'].keys():
            headers = self.auth()
            url = "{}/tags/{}/?op=nodes".format(self.maas.rstrip(), tag)
            request = requests.get(url, headers=headers)
            node_list = json.loads(request.text)
            for server in node_list:
              if server['zone']['name'] == Config.osh_config['region']:
                if (server['node_type_name'] == 'Machine' and server['status_name'] == 'Deployed') or server['node_type'] in [2,4]:
                  res['counts'][tag] += 1
                  if tag == 'osd-nodes':
                    journal = False
                    for disk in server['physicalblockdevice_set']:
                      if 'journal' in disk['tags']:
                        journal = True
                        break
                    if not journal:
                      print("Journal is absent on server {}. Verify tag 'journal' on disk in maas".format(server['hostname']))
                      sys.exit(1)
        if res['counts']['control-plane'] < Config.min_control_nodes:
          print("Not enouth control nodes in inventory in region {}. Verify tag 'control-plane' on servers in maas".format(Config.osh_config['region']))
          sys.exit(1)
        if res['counts']['compute-plane'] < Config.min_compute_nodes:
          print("Not enouth compute nodes in inventory in region {}. Verify tag 'compute-plane' on servers in maas".format(Config.osh_config['region']))
          sys.exit(1)
        if res['counts']['osd-nodes'] < Config.min_osd_nodes:
          print("Not enouth osd nodes in inventory in region {}. Verify tag 'osd-nodes' on servers in maas".format(Config.osh_config['region']))
          sys.exit(1)
          

    def inventory(self):
        """Look up hosts by tag(s) and zone(s) and return a dict that Ansible will understand as an inventory."""
        tags = self.tags()
        if False: # Now always false, for future use
          domain = "."+Config.osh_config['int_domain_suffix']
        else:
          domain = ""
        ansible = {}
        for tag in tags:
            headers = self.auth()
            url = "{}/tags/{}/?op=nodes".format(self.maas.rstrip(), tag)
            request = requests.get(url, headers=headers)
            response = json.loads(request.text)
            group_name = tag
            hosts = []
            for server in response:
              if server['zone']['name'] == Config.osh_config['region']:
                if (server['node_type_name'] == 'Machine' and server['status_name'] == 'Deployed') or server['node_type'] in [2,4]:
                    hosts.append(server['hostname']+domain)
                    ansible[group_name] = {
                        "hosts": hosts,
                        "vars": {}
                    }

        nodes = self.nodes()
        hosts_zone = []
        hosts_all = []
        for node in nodes:
           zone = node['zone']['name']
           if (node['node_type_name'] == 'Machine' and node['status_name'] != 'Deployed') and node['node_type'] not in [2,4]:
             continue
           if type(Config.osh_config['cinder_backup_to_region']) is str and zone == Config.osh_config['cinder_backup_to_region']:
             hosts_zone.append(node['hostname']+domain)
             ansible[zone] = {
                  "hosts": hosts_zone,       
                  "vars": {}
             }
           if zone == Config.osh_config['region']:
             hosts_all.append(node['hostname']+domain)

        ansible['all'] = {
           "hosts": hosts_all,       
           "vars": {
              'ansible_python_interpreter': '/usr/bin/python3',
              'ansible_ssh_private_key_file': '{{inventory_dir}}/../share_creds/maas.ssh.key',
              'ansible_user': 'ubuntu',
              'ansible_become': 'true'
           }
        }

        node_dump = self.nodes()
        nodes_meta = {
            '_meta': {
                'hostvars': {}
            }
        }
        
        for node in node_dump:
           zone = node['zone']['name']
           ext_ceph_zone = False
           my_zones = [Config.osh_config['region']]
           if type(Config.osh_config['cinder_backup_to_region']) is str:
             my_zones.append(Config.osh_config['cinder_backup_to_region'])
             if zone == Config.osh_config['cinder_backup_to_region']:
               ext_ceph_zone = True
           if zone in my_zones:
             if node['node_type'] in [2,4]:
               for iface in node['interface_set']:
                 try:
                   dhcp = iface['links'][0]['subnet']['vlan']['dhcp_on']
                   if dhcp:
                     if not ext_ceph_zone:
                       nodes_meta['_meta']['hostvars'][node['hostname']+domain] = {
                       'ansible_host': iface['links'][0]['ip_address'],
                        'ip': self.getip(iface['links'][0]['ip_address']),
                       'rack_ctl': 'true',
                       }
                       nodes_meta['_meta']['hostvars'][node['hostname']+domain].update(self.get_iface_type(node['interface_set']))
                     else:
                       nodes_meta['_meta']['hostvars'][node['hostname']+domain] = {
                       'ansible_host': iface['links'][0]['ip_address'],
                       }
                       nodes_meta['_meta']['hostvars'][node['hostname']+domain].update(self.get_iface_type(node['interface_set']))
                 except:
                   continue
             elif node['node_type_name'] == 'Machine' and node['status_name'] == 'Deployed':
               if not node['tag_names']:
                 pass
               else:
                 if not ext_ceph_zone:
                   nodes_meta['_meta']['hostvars'][node['hostname']+domain] = {
                     'ansible_host': node['ip_addresses'][0],
                     'ip': self.getip(node['ip_addresses'][0]),
                   } 
                   nodes_meta['_meta']['hostvars'][node['hostname']+domain].update(self.get_iface_type(node['interface_set']))
                   if 'osd-nodes' in node['tag_names']:
                     disks = []
                     journal_disk = ""
                     for disk in node['physicalblockdevice_set']:
                       disks.append(disk['name'])
                       if 'journal' in disk['tags']:
                         journal_disk = disk['name']
                         nodes_meta['_meta']['hostvars'][node['hostname']+domain]['osd_jour'] = disk['name']
                     if journal_disk:
                       nodes_meta['_meta']['hostvars'][node['hostname']+domain]['osd_disks'] = list(set(disks).difference([node['boot_disk']['name'],journal_disk]))
                 else:
                   nodes_meta['_meta']['hostvars'][node['hostname']+domain] = {
                     'ansible_host': node['ip_addresses'][0],
                   } 
                   nodes_meta['_meta']['hostvars'][node['hostname']+domain].update(self.get_iface_type(node['interface_set']))

        # Add some static groups
#        ansible['ungrouped'] = {}
        ansible['kube-master'] = {
          'hosts': [],
          'vars': {},
          'children': ['control-plane']
        }
        ansible['etcd'] = {
          'hosts': [],
          'vars': {},
          'children': ['control-plane']
        }
        ansible['kube-node'] = {
          'hosts': [],
          'vars': {},
          'children': ['control-plane', 'compute-plane', 'osd-nodes']
        }
        ansible['k8s-cluster'] = {
          'hosts': [],
          'vars': {},
          'children': ['kube-master', 'kube-node']
        }
        ansible['master'] = {
          'hosts': ['localhost'],
          'vars': {
            'ansible_connection': 'local',
          }
        }

        # Need to merge ansible and nodes dict()s as a shallow copy, or Ansible shits itself and throws an error
        result = ansible.copy()
        result.update(nodes_meta)
        return result

    def get_iface_type(self, iface_set):
        result = {}
        for iface in iface_set:
          if iface['type'] == 'bond':
            result['iface_type'] = iface['type']
            result['bond_name'] = iface['name']
            break
        if not result.has_key('iface_type'):
          result['iface_type'] = 'interface'
        return result

    def getip(self, src_ip):
        dest_net = ipaddress.ip_network(Config.osh_config['k8s']['net'].decode('utf-8'))
        prefix = dest_net.prefixlen
        src_ip_mask = ipaddress.IPv4Interface("{}/{}".format(src_ip,prefix).decode('utf-8'))
        src_net = ipaddress.ip_network(str(src_ip_mask.network).decode('utf-8'))
        host_ip = int(ipaddress.ip_address(src_ip)) - int(src_net.network_address)
        ip = ipaddress.ip_address(int(dest_net.network_address) + host_ip)
        return str(ip)

    def nodes(self):
        """Return a list of nodes from the MAAS API."""
        headers = self.auth()
        url = "%s/nodes/" % self.maas.rstrip()
        request = requests.get(url, headers=headers)
        response = json.loads(request.text)
        return response

    def cli_handler(self):
        """Manage command line options and arguments."""
        parser = argparse.ArgumentParser(description='Dynamically produce an Ansible inventory from Ubuntu MAAS.', add_help=False)
        parser.add_argument('-l', '--list', action='store_true', help='List instances by tag. (default)')
        parser.add_argument('-h', '--host', action='store', help='Get variables relating to a specific instance.')
        parser.add_argument('-n', '--nodes', action='store_true', help='List all nodes registered under MAAS.')
        parser.add_argument('-t', '--tags', action='store_true', help='List all tags registered under MAAS.')
        parser.add_argument('--tag', action='store', help='Get details for a specific tag registered under MAAS.')
        parser.add_argument('-s', '--supported', action='store_true', help='List which MAAS API version are supported.')
        parser.add_argument('--help', action='help', help='Show this help message and exit.')

        # Be kind and print help when no arguments given.
        if len(sys.argv)==1:
            parser.print_help()
            sys.exit(1)

        self.args = parser.parse_args()

if __name__ == "__main__":
    Inventory()
