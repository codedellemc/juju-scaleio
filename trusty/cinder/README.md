Overview
--------

This charm provides the Cinder volume service for OpenStack.  It is intended to
be used alongside the other OpenStack components, starting with the Folsom
release.

Cinder is made up of 3 separate services: an API service, a scheduler and a
volume service.  This charm allows them to be deployed in different
combination, depending on user preference and requirements.

This charm was developed to support deploying Folsom on both
Ubuntu Quantal and Ubuntu Precise.  Since Cinder is only available for
Ubuntu 12.04 via the Ubuntu Cloud Archive, deploying this charm to a
Precise machine will by default install Cinder and its dependencies from
the Cloud Archive.

Usage
-----

Cinder may be deployed in a number of ways.  This charm focuses on 3 main
configurations.  All require the existence of the other core OpenStack
services deployed via Juju charms, specifically: mysql, rabbitmq-server,
keystone and nova-cloud-controller.  The following assumes these services
have already been deployed.

Basic, all-in-one using local storage and iSCSI
===============================================

The api server, scheduler and volume service are all deployed into the same
unit.  Local storage will be initialized as a LVM phsyical device, and a volume
group initialized.  Instance volumes will be created locally as logical volumes
and exported to instances via iSCSI.  This is ideal for small-scale deployments
or testing:

    cat >cinder.cfg <<END
    cinder:
        block-device: sdc
        overwrite: true
    END
    juju deploy --config=cinder.cfg cinder
    juju add-relation cinder keystone
    juju add-relation cinder mysql
    juju add-relation cinder rabbitmq-server
    juju add-relation cinder nova-cloud-controller

Separate volume units for scale out, using local storage and iSCSI
==================================================================

Separating the volume service from the API service allows the storage pool
to easily scale without the added complexity that accompanies load-balancing
the API server.  When we've exhausted local storage on volume server, we can
simply add-unit to expand our capacity.  Future requests to allocate volumes
will be distributed across the pool of volume servers according to the
availability of storage space.

    cat >cinder.cfg <<END
    cinder-api:
        enabled-services: api, scheduler
    cinder-volume:
        enabled-services: volume
        block-device: sdc
        overwrite: true
    END
    juju deploy --config=cinder.cfg cinder cinder-api
    juju deploy --config=cinder.cfg cinder cinder-volume
    juju add-relation cinder-api mysql
    juju add-relation cinder-api rabbitmq-server
    juju add-relation cinder-api keystone
    juju add-relation cinder-api nova-cloud-controller
    juju add-relation cinder-volume mysql
    juju add-relation cinder-volume rabbitmq-server

    # When more storage is needed, simply add more volume servers.
    juju add-unit cinder-volume

All-in-one using Ceph-backed RBD volumes
========================================

All 3 services can be deployed to the same unit, but instead of relying
on local storage to back volumes an external Ceph cluster is used.  This
allows scalability and redundancy needs to be satisified and Cinder's RBD
driver used to create, export and connect volumes to instances.  This assumes
a functioning Ceph cluster has already been deployed using the official Ceph
charm and a relation exists between the Ceph service and the nova-compute
service.

    cat >cinder.cfg <<END
    cinder:
        block-device: None
    END
    juju deploy --config=cinder.cfg cinder
    juju add-relation cinder ceph
    juju add-relation cinder keystone
    juju add-relation cinder mysql
    juju add-relation cinder rabbitmq-server
    juju add-relation cinder nova-cloud-controller


Configuration
-------------

The default value for most config options should work for most deployments.

Users should be aware of three options, in particular:

openstack-origin:  Allows Cinder to be installed from a specific apt repository.
                   See config.yaml for a list of supported sources.

block-device:  When using local storage, a block device should be specified to
               back a LVM volume group.  It's important this device exists on
               all nodes that the service may be deployed to.

overwrite:  Whether or not to wipe local storage that of data that may prevent
            it from being initialized as a LVM phsyical device.  This includes
            filesystems and partition tables.  *CAUTION*

enabled-services:  Can be used to separate cinder services between service
                   service units (see previous section)

Deploying from source
---------------------

The minimum openstack-origin-git config required to deploy from source is:

    openstack-origin-git: include-file://cinder-juno.yaml

    cinder-juno.yaml
        repositories:
        - {name: requirements,
           repository: 'git://github.com/openstack/requirements',
           branch: stable/juno}
        - {name: cinder,
           repository: 'git://github.com/openstack/cinder',
           branch: stable/juno}

Note that there are only two 'name' values the charm knows about: 'requirements'
and 'cinder'. These repositories must correspond to these 'name' values.
Additionally, the requirements repository must be specified first and the
cinder repository must be specified last. All other repostories are installed
in the order in which they are specified.

The following is a full list of current tip repos (may not be up-to-date):

    openstack-origin-git: include-file://cinder-master.yaml

    cinder-master.yaml
        repositories:
        - {name: requirements,
           repository: 'git://github.com/openstack/requirements',
           branch: master}
        - {name: oslo-concurrency,
           repository: 'git://github.com/openstack/oslo.concurrency',
           branch: master}
        - {name: oslo-config,
           repository: 'git://github.com/openstack/oslo.config',
           branch: master}
        - {name: oslo-context,
           repository': 'git://github.com/openstack/oslo.context',
           branch: master}
        - {name: oslo-db,
           repository: 'git://github.com/openstack/oslo.db',
           branch: master}
        - {name: oslo-i18n,
           repository: 'git://github.com/openstack/oslo.i18n',
           branch: master}
        - {name: oslo-messaging,
           repository: 'git://github.com/openstack/oslo.messaging',
           branch: master}
        - {name: oslo-serialization,
           repository: 'git://github.com/openstack/oslo.serialization',
           branch: master}
        - {name: oslo-utils,
           repository: 'git://github.com/openstack/oslo.utils',
           branch: master}
        - {name: oslo-rootwrap,
           repository: 'git://github.com/openstack/oslo.rootwrap',
           branch: master}
        - {name: oslo-vmware,
           repository: 'git://github.com/openstack/oslo.vmware',
           branch: master}
        - {name: osprofiler,
           repository: 'git://github.com/stackforge/osprofiler',
           branch: master}
        - {name: pbr,
           repository: 'git://github.com/openstack-dev/pbr',
           branch: master}
        - {name: python-barbicanclient,
           repository: 'git://github.com/openstack/python-barbicanclient',
           branch: master}
        - {name: python-glanceclient,
           repository: 'git://github.com/openstack/python-glanceclient',
           branch: master}
        - {name: python-novaclient,
           repository: 'git://github.com/openstack/python-novaclient',
           branch: master}
        - {name: python-swiftclient:
           repository: 'git://github.com/openstack/python-swiftclient',
           branch: master}
        - {name: sqlalchemy-migrate,
           repository: 'git://github.com/stackforge/sqlalchemy-migrate',
           branch: master}
        - {name: stevedore,
           repository: 'git://github.com/openstack/stevedore',
           branch: master}
        - {name: taskflow,
           repository: 'git://github.com/openstack/taskflow',
           branch: master}
        - {name: keystonemiddleware,
           repository: 'git://github.com/openstack/keystonemiddleware',
           branch: master}
        - {name: cinder,
           repository: 'git://github.com/openstack/cinder',
           branch: master}

Network Space support
---------------------

This charm supports the use of Juju Network Spaces, allowing the charm to be bound to network space configurations managed directly by Juju.  This is only supported with Juju 2.0 and above.

API endpoints can be bound to distinct network spaces supporting the network separation of public, internal and admin endpoints.

Access to the underlying MySQL instance can also be bound to a specific space using the shared-db relation.

To use this feature, use the --bind option when deploying the charm:

    juju deploy cinder --bind "public=public-space internal=internal-space admin=admin-space shared-db=internal-space"

alternatively these can also be provided as part of a juju native bundle configuration:

    cinder:
      charm: cs:xenial/cinder
      num_units: 1
      bindings:
        public: public-space
        admin: admin-space
        internal: internal-space
        shared-db: internal-space

NOTE: Spaces must be configured in the underlying provider prior to attempting to use them.

NOTE: Existing deployments using os-*-network configuration options will continue to function; these options are preferred over any network space binding provided if set.
