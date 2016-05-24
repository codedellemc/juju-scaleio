from mock import patch, call, MagicMock, Mock
from test_utils import CharmTestCase
import os

os.environ['JUJU_UNIT_NAME'] = 'keystone'
with patch('charmhelpers.core.hookenv.config') as config:
    import keystone_utils as utils

TO_PATCH = [
    'api_port',
    'config',
    'os_release',
    'log',
    'get_ca',
    'create_role',
    'create_service_entry',
    'create_endpoint_template',
    'get_admin_token',
    'get_local_endpoint',
    'get_requested_roles',
    'get_service_password',
    'get_os_codename_install_source',
    'grant_role',
    'configure_installation_source',
    'is_elected_leader',
    'is_ssl_cert_master',
    'https',
    'peer_store_and_set',
    'service_stop',
    'service_start',
    'relation_get',
    'relation_set',
    'relation_ids',
    'relation_id',
    'local_unit',
    'related_units',
    'https',
    'is_relation_made',
    'peer_store',
    'pip_install',
    # generic
    'apt_update',
    'apt_upgrade',
    'apt_install',
    'subprocess',
    'time',
    'pwgen',
]

openstack_origin_git = \
    """repositories:
         - {name: requirements,
            repository: 'git://git.openstack.org/openstack/requirements',
            branch: stable/juno}
         - {name: keystone,
            repository: 'git://git.openstack.org/openstack/keystone',
            branch: stable/juno}"""


class TestKeystoneUtils(CharmTestCase):

    def setUp(self):
        super(TestKeystoneUtils, self).setUp(utils, TO_PATCH)
        self.config.side_effect = self.test_config.get

        self.ctxt = MagicMock()
        self.rsc_map = {
            '/etc/keystone/keystone.conf': {
                'services': ['keystone'],
                'contexts': [self.ctxt],
            },
            '/etc/apache2/sites-available/openstack_https_frontend': {
                'services': ['apache2'],
                'contexts': [self.ctxt],
            },
            '/etc/apache2/sites-available/openstack_https_frontend.conf': {
                'services': ['apache2'],
                'contexts': [self.ctxt],
            }
        }

    @patch('charmhelpers.contrib.openstack.templating.OSConfigRenderer')
    @patch('os.path.exists')
    @patch.object(utils, 'resource_map')
    def test_register_configs_apache(self, resource_map, exists, renderer):
        exists.return_value = False
        self.os_release.return_value = 'havana'
        fake_renderer = MagicMock()
        fake_renderer.register = MagicMock()
        renderer.return_value = fake_renderer

        resource_map.return_value = self.rsc_map
        utils.register_configs()
        renderer.assert_called_with(
            openstack_release='havana', templates_dir='templates/')

        ex_reg = [
            call('/etc/keystone/keystone.conf', [self.ctxt]),
            call(
                '/etc/apache2/sites-available/openstack_https_frontend',
                [self.ctxt]),
            call(
                '/etc/apache2/sites-available/openstack_https_frontend.conf',
                [self.ctxt]),
        ]
        self.assertEquals(fake_renderer.register.call_args_list, ex_reg)

    def test_determine_ports(self):
        self.test_config.set('admin-port', '80')
        self.test_config.set('service-port', '81')
        result = utils.determine_ports()
        self.assertEquals(result, ['80', '81'])

    @patch('charmhelpers.contrib.openstack.utils.config')
    def test_determine_packages(self, _config):
        _config.return_value = None
        result = utils.determine_packages()
        ex = utils.BASE_PACKAGES + ['keystone', 'python-keystoneclient']
        self.assertEquals(set(ex), set(result))

    @patch('charmhelpers.contrib.openstack.utils.config')
    def test_determine_packages_git(self, _config):
        _config.return_value = openstack_origin_git
        result = utils.determine_packages()
        ex = utils.BASE_PACKAGES + utils.BASE_GIT_PACKAGES
        for p in utils.GIT_PACKAGE_BLACKLIST:
            ex.remove(p)
        self.assertEquals(set(ex), set(result))

    @patch.object(utils, 'determine_packages')
    @patch.object(utils, 'migrate_database')
    def test_openstack_upgrade_leader(
            self, migrate_database, determine_packages):
        configs = MagicMock()
        self.test_config.set('openstack-origin', 'precise')
        determine_packages.return_value = []
        self.is_elected_leader.return_value = True

        utils.do_openstack_upgrade(configs)

        self.get_os_codename_install_source.assert_called_with('precise')
        self.configure_installation_source.assert_called_with('precise')
        self.assertTrue(self.apt_update.called)

        dpkg_opts = [
            '--option', 'Dpkg::Options::=--force-confnew',
            '--option', 'Dpkg::Options::=--force-confdef',
        ]
        self.apt_upgrade.assert_called_with(
            options=dpkg_opts,
            fatal=True,
            dist=True)
        self.apt_install.assert_called_with(
            packages=[],
            options=dpkg_opts,
            fatal=True)

        self.assertTrue(configs.set_release.called)
        self.assertTrue(configs.write_all.called)
        self.assertTrue(migrate_database.called)

    def test_migrate_database(self):
        utils.migrate_database()

        self.service_stop.assert_called_with('keystone')
        cmd = ['sudo', '-u', 'keystone', 'keystone-manage', 'db_sync']
        self.subprocess.check_output.assert_called_with(cmd)
        self.service_start.assert_called_with('keystone')

    @patch.object(utils, 'get_manager')
    @patch.object(utils, 'resolve_address')
    @patch.object(utils, 'b64encode')
    def test_add_service_to_keystone_clustered_https_none_values(
            self, b64encode, _resolve_address, _get_manager):
        relation_id = 'identity-service:0'
        remote_unit = 'unit/0'
        _resolve_address.return_value = '10.10.10.10'
        self.https.return_value = True
        self.test_config.set('https-service-endpoints', 'True')
        self.test_config.set('vip', '10.10.10.10')
        self.test_config.set('admin-port', 80)
        self.test_config.set('service-port', 81)
        b64encode.return_value = 'certificate'
        self.get_requested_roles.return_value = ['role1', ]

        self.relation_get.return_value = {'service': 'keystone',
                                          'region': 'RegionOne',
                                          'public_url': 'None',
                                          'admin_url': '10.0.0.2',
                                          'internal_url': '192.168.1.2'}

        utils.add_service_to_keystone(
            relation_id=relation_id,
            remote_unit=remote_unit)
        self.assertTrue(self.https.called)
        self.assertTrue(self.create_role.called)

        relation_data = {'auth_host': '10.10.10.10',
                         'service_host': '10.10.10.10',
                         'auth_protocol': 'https',
                         'service_protocol': 'https',
                         'auth_port': 80,
                         'service_port': 81,
                         'https_keystone': 'True',
                         'ca_cert': 'certificate',
                         'region': 'RegionOne'}
        self.peer_store_and_set.assert_called_with(relation_id=relation_id,
                                                   **relation_data)

    @patch.object(utils, 'create_user')
    @patch.object(utils, 'resolve_address')
    @patch.object(utils, 'ensure_valid_service')
    @patch.object(utils, 'add_endpoint')
    @patch.object(utils, 'get_manager')
    def test_add_service_to_keystone_no_clustered_no_https_complete_values(
            self, KeystoneManager, add_endpoint, ensure_valid_service,
            _resolve_address, create_user):
        relation_id = 'identity-service:0'
        remote_unit = 'unit/0'
        self.get_admin_token.return_value = 'token'
        self.get_service_password.return_value = 'password'
        self.test_config.set('service-tenant', 'tenant')
        self.test_config.set('admin-role', 'admin')
        self.get_requested_roles.return_value = ['role1', ]
        _resolve_address.return_value = '10.0.0.3'
        self.test_config.set('admin-port', 80)
        self.test_config.set('service-port', 81)
        self.https.return_value = False
        self.test_config.set('https-service-endpoints', 'False')
        self.get_local_endpoint.return_value = 'http://localhost:80/v2.0/'
        self.relation_ids.return_value = ['cluster/0']

        mock_keystone = MagicMock()
        mock_keystone.resolve_tenant_id.return_value = 'tenant_id'
        KeystoneManager.return_value = mock_keystone

        self.relation_get.return_value = {'service': 'keystone',
                                          'region': 'RegionOne',
                                          'public_url': '10.0.0.1',
                                          'admin_url': '10.0.0.2',
                                          'internal_url': '192.168.1.2'}

        utils.add_service_to_keystone(
            relation_id=relation_id,
            remote_unit=remote_unit)
        ensure_valid_service.assert_called_with('keystone')
        add_endpoint.assert_called_with(region='RegionOne', service='keystone',
                                        publicurl='10.0.0.1',
                                        adminurl='10.0.0.2',
                                        internalurl='192.168.1.2')
        self.assertTrue(self.get_admin_token.called)
        self.get_service_password.assert_called_with('keystone')
        create_user.assert_called_with('keystone', 'password', 'tenant', None)
        self.grant_role.assert_called_with('keystone', 'Admin', 'tenant',
                                           None)
        self.create_role.assert_called_with('role1', 'keystone', 'tenant',
                                            None)

        relation_data = {'auth_host': '10.0.0.3', 'service_host': '10.0.0.3',
                         'admin_token': 'token', 'service_port': 81,
                         'auth_port': 80, 'service_username': 'keystone',
                         'service_password': 'password',
                         'service_tenant': 'tenant',
                         'https_keystone': '__null__',
                         'ssl_cert': '__null__', 'ssl_key': '__null__',
                         'ca_cert': '__null__',
                         'auth_protocol': 'http', 'service_protocol': 'http',
                         'service_tenant_id': 'tenant_id', 'api_version': 2}

        filtered = {}
        for k, v in relation_data.iteritems():
            if v == '__null__':
                filtered[k] = None
            else:
                filtered[k] = v

        self.assertTrue(self.relation_set.called)
        self.peer_store_and_set.assert_called_with(relation_id=relation_id,
                                                   **relation_data)
        self.relation_set.assert_called_with(relation_id=relation_id,
                                             **filtered)

    @patch('charmhelpers.contrib.openstack.ip.config')
    @patch.object(utils, 'ensure_valid_service')
    @patch.object(utils, 'add_endpoint')
    @patch.object(utils, 'get_manager')
    def test_add_service_to_keystone_nosubset(
            self, KeystoneManager, add_endpoint, ensure_valid_service,
            ip_config):
        relation_id = 'identity-service:0'
        remote_unit = 'unit/0'

        self.relation_get.return_value = {'ec2_service': 'nova',
                                          'ec2_region': 'RegionOne',
                                          'ec2_public_url': '10.0.0.1',
                                          'ec2_admin_url': '10.0.0.2',
                                          'ec2_internal_url': '192.168.1.2'}
        self.get_local_endpoint.return_value = 'http://localhost:80/v2.0/'
        KeystoneManager.resolve_tenant_id.return_value = 'tenant_id'

        utils.add_service_to_keystone(
            relation_id=relation_id,
            remote_unit=remote_unit)
        ensure_valid_service.assert_called_with('nova')
        add_endpoint.assert_called_with(region='RegionOne', service='nova',
                                        publicurl='10.0.0.1',
                                        adminurl='10.0.0.2',
                                        internalurl='192.168.1.2')

    @patch.object(utils, 'user_exists')
    @patch.object(utils, 'grant_role')
    @patch.object(utils, 'create_role')
    @patch.object(utils, 'create_user')
    def test_create_user_credentials_no_roles(self, mock_create_user,
                                              mock_create_role,
                                              mock_grant_role,
                                              mock_user_exists):
        mock_user_exists.return_value = False
        utils.create_user_credentials('userA', 'passA', tenant='tenantA')
        mock_create_user.assert_has_calls([call('userA', 'passA', 'tenantA',
                                                None)])
        mock_create_role.assert_has_calls([])
        mock_grant_role.assert_has_calls([])

    @patch.object(utils, 'user_exists')
    @patch.object(utils, 'grant_role')
    @patch.object(utils, 'create_role')
    @patch.object(utils, 'create_user')
    def test_create_user_credentials(self, mock_create_user, mock_create_role,
                                     mock_grant_role, mock_user_exists):
        mock_user_exists.return_value = False
        utils.create_user_credentials('userA', 'passA', tenant='tenantA',
                                      grants=['roleA'], new_roles=['roleB'])
        mock_create_user.assert_has_calls([call('userA', 'passA', 'tenantA',
                                                None)])
        mock_create_role.assert_has_calls([call('roleB', 'userA', 'tenantA',
                                                None)])
        mock_grant_role.assert_has_calls([call('userA', 'roleA', 'tenantA',
                                          None)])

    @patch.object(utils, 'update_user_password')
    @patch.object(utils, 'user_exists')
    @patch.object(utils, 'grant_role')
    @patch.object(utils, 'create_role')
    @patch.object(utils, 'create_user')
    def test_create_user_credentials_user_exists(self, mock_create_user,
                                                 mock_create_role,
                                                 mock_grant_role,
                                                 mock_user_exists,
                                                 mock_update_user_password):
        mock_user_exists.return_value = True
        utils.create_user_credentials('userA', 'passA', tenant='tenantA',
                                      grants=['roleA'], new_roles=['roleB'])
        mock_create_user.assert_has_calls([])
        mock_create_role.assert_has_calls([call('roleB', 'userA', 'tenantA',
                                                None)])
        mock_grant_role.assert_has_calls([call('userA', 'roleA', 'tenantA',
                                               None)])
        mock_update_user_password.assert_has_calls([call('userA', 'passA')])

    @patch.object(utils, 'get_manager')
    def test_create_user_case_sensitivity(self, KeystoneManager):
        """ Test case sensitivity of check for existence in
            the user creation process """
        mock_keystone = MagicMock()
        KeystoneManager.return_value = mock_keystone

        mock_user = MagicMock()
        mock_keystone.resolve_user_id.return_value = mock_user
        mock_keystone.api.users.list.return_value = [mock_user]

        # User found is the same i.e. userA == userA
        mock_user.name = 'userA'
        utils.create_user('userA', 'passA')
        mock_keystone.resolve_user_id.assert_called_with('userA',
                                                         user_domain=None)
        mock_keystone.create_user.assert_not_called()

        # User found has different case but is the same
        # i.e. Usera != userA
        mock_user.name = 'Usera'
        utils.create_user('userA', 'passA')
        mock_keystone.resolve_user_id.assert_called_with('userA',
                                                         user_domain=None)
        mock_keystone.create_user.assert_not_called()

        # User is different i.e. UserB != userA
        mock_user.name = 'UserB'
        utils.create_user('userA', 'passA')
        mock_keystone.resolve_user_id.assert_called_with('userA',
                                                         user_domain=None)
        mock_keystone.create_user.assert_called_with(name='userA',
                                                     password='passA',
                                                     tenant_id=None,
                                                     domain_id=None,
                                                     email='juju@localhost')

    @patch.object(utils, 'get_service_password')
    @patch.object(utils, 'create_user_credentials')
    def test_create_service_credentials(self, mock_create_user_credentials,
                                        mock_get_service_password):
        mock_get_service_password.return_value = 'passA'
        cfg = {'service-tenant': 'tenantA', 'admin-role': 'Admin',
               'preferred-api-version': 2}
        self.config.side_effect = lambda key: cfg.get(key, None)
        calls = [call('serviceA', 'passA', domain=None, grants=['Admin'],
                      new_roles=None, tenant='tenantA')]

        utils.create_service_credentials('serviceA')
        mock_create_user_credentials.assert_has_calls(calls)

    def test_ensure_valid_service_incorrect(self):
        utils.ensure_valid_service('fakeservice')
        self.log.assert_called_with("Invalid service requested: 'fakeservice'")
        self.relation_set.assert_called_with(admin_token=-1)

    def test_add_endpoint(self):
        publicurl = '10.0.0.1'
        adminurl = '10.0.0.2'
        internalurl = '10.0.0.3'
        utils.add_endpoint(
            'RegionOne',
            'nova',
            publicurl,
            adminurl,
            internalurl)
        self.create_service_entry.assert_called_with(
            'nova',
            'compute',
            'Nova Compute Service')
        self.create_endpoint_template.asssert_called_with(
            region='RegionOne', service='nova',
            publicurl=publicurl, adminurl=adminurl,
            internalurl=internalurl)

    @patch.object(utils, 'uuid')
    @patch.object(utils, 'relation_set')
    @patch.object(utils, 'relation_get')
    @patch.object(utils, 'relation_ids')
    @patch.object(utils, 'is_elected_leader')
    def test_send_notifications(self, mock_is_elected_leader,
                                mock_relation_ids, mock_relation_get,
                                mock_relation_set, mock_uuid):
        relation_id = 'testrel:0'
        mock_uuid.uuid4.return_value = '1234'
        mock_relation_ids.return_value = [relation_id]
        mock_is_elected_leader.return_value = False
        utils.send_notifications({'foo-endpoint-changed': 1})
        self.assertFalse(mock_relation_set.called)

        mock_is_elected_leader.return_value = True
        utils.send_notifications({})
        self.assertFalse(mock_relation_set.called)

        settings = {'foo-endpoint-changed': 1}
        utils.send_notifications(settings)
        self.assertTrue(mock_relation_set.called)
        mock_relation_set.assert_called_once_with(relation_id=relation_id,
                                                  relation_settings=settings)
        mock_relation_set.reset_mock()
        settings = {'foo-endpoint-changed': 1}
        utils.send_notifications(settings, force=True)
        self.assertTrue(mock_relation_set.called)
        settings['trigger'] = '1234'
        mock_relation_set.assert_called_once_with(relation_id=relation_id,
                                                  relation_settings=settings)

    def test_get_admin_passwd_pwd_set(self):
        self.test_config.set('admin-password', 'supersecret')
        self.assertEqual(utils.get_admin_passwd(), 'supersecret')

    @patch('os.path.isfile')
    def test_get_admin_passwd_pwd_file_load(self, isfile):
        self.test_config.set('admin-password', '')
        isfile.return_value = True
        with patch('__builtin__.open') as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = Mock()
            mock_open.return_value.readline.return_value = 'supersecretfilepwd'
            self.assertEqual(utils.get_admin_passwd(), 'supersecretfilepwd')

    @patch.object(utils, 'store_admin_passwd')
    @patch('os.path.isfile')
    def test_get_admin_passwd_genpass(self, isfile, store_admin_passwd):
        self.test_config.set('admin-password', '')
        isfile.return_value = False
        self.subprocess.check_output.return_value = 'supersecretgen'
        self.assertEqual(utils.get_admin_passwd(), 'supersecretgen')

    def test_is_db_ready(self):
        allowed_units = None

        def fake_rel_get(attribute=None, *args, **kwargs):
            if attribute == 'allowed_units':
                return allowed_units

        self.relation_get.side_effect = fake_rel_get

        self.relation_id.return_value = 'shared-db:0'
        self.relation_ids.return_value = ['shared-db:0']
        self.local_unit.return_value = 'unit/0'
        allowed_units = 'unit/0'
        self.assertTrue(utils.is_db_ready(use_current_context=True))

        self.relation_id.return_value = 'shared-db:0'
        self.relation_ids.return_value = ['shared-db:0']
        self.local_unit.return_value = 'unit/0'
        allowed_units = 'unit/1'
        self.assertFalse(utils.is_db_ready(use_current_context=True))

        self.relation_ids.return_value = ['acme:0']
        self.assertRaises(utils.is_db_ready, use_current_context=True)

        allowed_units = 'unit/0'
        self.related_units.return_value = ['unit/0']
        self.relation_ids.return_value = ['shared-db:0', 'shared-db:1']
        self.assertTrue(utils.is_db_ready())

        allowed_units = 'unit/1'
        self.assertFalse(utils.is_db_ready())

        self.related_units.return_value = []
        self.assertTrue(utils.is_db_ready())

    @patch.object(utils, 'peer_units')
    def test_ensure_ssl_cert_master_ssl_no_peers(self, mock_peer_units):
        def mock_rel_get(unit=None, **kwargs):
            return None

        self.relation_get.side_effect = mock_rel_get
        self.relation_ids.return_value = ['cluster:0']
        self.local_unit.return_value = 'unit/0'
        self.related_units.return_value = []
        mock_peer_units.return_value = []
        # This should get ignored since we are overriding
        self.is_ssl_cert_master.return_value = False
        self.is_elected_leader.return_value = False
        self.assertTrue(utils.ensure_ssl_cert_master())
        settings = {'ssl-cert-master': 'unit/0'}
        self.relation_set.assert_called_with(relation_id='cluster:0',
                                             relation_settings=settings)

    @patch.object(utils, 'peer_units')
    def test_ensure_ssl_cert_master_ssl_master_no_peers(self,
                                                        mock_peer_units):
        def mock_rel_get(unit=None, **kwargs):
            if unit == 'unit/0':
                return 'unit/0'

            return None

        self.relation_get.side_effect = mock_rel_get
        self.relation_ids.return_value = ['cluster:0']
        self.local_unit.return_value = 'unit/0'
        self.related_units.return_value = []
        mock_peer_units.return_value = []
        # This should get ignored since we are overriding
        self.is_ssl_cert_master.return_value = False
        self.is_elected_leader.return_value = False
        self.assertTrue(utils.ensure_ssl_cert_master())
        settings = {'ssl-cert-master': 'unit/0'}
        self.relation_set.assert_called_with(relation_id='cluster:0',
                                             relation_settings=settings)

    @patch.object(utils, 'peer_units')
    def test_ensure_ssl_cert_master_ssl_not_leader(self, mock_peer_units):
        self.relation_ids.return_value = ['cluster:0']
        self.local_unit.return_value = 'unit/0'
        mock_peer_units.return_value = ['unit/1']
        self.is_ssl_cert_master.return_value = False
        self.is_elected_leader.return_value = False
        self.assertFalse(utils.ensure_ssl_cert_master())
        self.assertFalse(self.relation_set.called)

    @patch.object(utils, 'peer_units')
    def test_ensure_ssl_cert_master_is_leader_new_peer(self,
                                                       mock_peer_units):
        def mock_rel_get(unit=None, **kwargs):
            if unit == 'unit/0':
                return 'unit/0'

            return 'unknown'

        self.relation_get.side_effect = mock_rel_get
        self.relation_ids.return_value = ['cluster:0']
        self.local_unit.return_value = 'unit/0'
        mock_peer_units.return_value = ['unit/1']
        self.related_units.return_value = ['unit/1']
        self.is_ssl_cert_master.return_value = False
        self.is_elected_leader.return_value = True
        self.assertFalse(utils.ensure_ssl_cert_master())
        settings = {'ssl-cert-master': 'unit/0'}
        self.relation_set.assert_called_with(relation_id='cluster:0',
                                             relation_settings=settings)

    @patch.object(utils, 'peer_units')
    def test_ensure_ssl_cert_master_is_leader_no_new_peer(self,
                                                          mock_peer_units):
        def mock_rel_get(unit=None, **kwargs):
            if unit == 'unit/0':
                return 'unit/0'

            return 'unit/0'

        self.relation_get.side_effect = mock_rel_get
        self.relation_ids.return_value = ['cluster:0']
        self.local_unit.return_value = 'unit/0'
        mock_peer_units.return_value = ['unit/1']
        self.related_units.return_value = ['unit/1']
        self.is_ssl_cert_master.return_value = False
        self.is_elected_leader.return_value = True
        self.assertFalse(utils.ensure_ssl_cert_master())
        self.assertFalse(self.relation_set.called)

    @patch('charmhelpers.contrib.openstack.ip.unit_get')
    @patch('charmhelpers.contrib.openstack.ip.is_clustered')
    @patch('charmhelpers.contrib.openstack.ip.config')
    @patch.object(utils, 'create_keystone_endpoint')
    @patch.object(utils, 'create_tenant')
    @patch.object(utils, 'create_user_credentials')
    @patch.object(utils, 'create_service_entry')
    def test_ensure_initial_admin_public_name(self,
                                              _create_service_entry,
                                              _create_user_creds,
                                              _create_tenant,
                                              _create_keystone_endpoint,
                                              _ip_config,
                                              _is_clustered,
                                              _unit_get):
        _is_clustered.return_value = False
        _ip_config.side_effect = self.test_config.get
        _unit_get.return_value = '10.0.0.1'
        self.test_config.set('os-public-hostname', 'keystone.example.com')
        utils.ensure_initial_admin(self.config)
        _create_keystone_endpoint.assert_called_with(
            public_ip='keystone.example.com',
            service_port=5000,
            internal_ip='10.0.0.1',
            admin_ip='10.0.0.1',
            auth_port=35357,
            region='RegionOne',
        )

    @patch.object(utils, 'peer_units')
    def test_ensure_ssl_cert_master_is_leader_bad_votes(self,
                                                        mock_peer_units):
        counter = {0: 0}

        def mock_rel_get(unit=None, **kwargs):
            """Returns a mix of votes."""
            if unit == 'unit/0':
                return 'unit/0'

            ret = 'unit/%d' % (counter[0])
            counter[0] += 1
            return ret

        self.relation_get.side_effect = mock_rel_get
        self.relation_ids.return_value = ['cluster:0']
        self.local_unit.return_value = 'unit/0'
        mock_peer_units.return_value = ['unit/1']
        self.related_units.return_value = ['unit/1']
        self.is_ssl_cert_master.return_value = False
        self.is_elected_leader.return_value = True
        self.assertFalse(utils.ensure_ssl_cert_master())
        self.assertFalse(self.relation_set.called)

    @patch.object(utils, 'git_install_requested')
    @patch.object(utils, 'git_clone_and_install')
    @patch.object(utils, 'git_post_install')
    @patch.object(utils, 'git_pre_install')
    def test_git_install(self, git_pre, git_post, git_clone_and_install,
                         git_requested):
        projects_yaml = openstack_origin_git
        git_requested.return_value = True
        utils.git_install(projects_yaml)
        self.assertTrue(git_pre.called)
        git_clone_and_install.assert_called_with(openstack_origin_git,
                                                 core_project='keystone')
        self.assertTrue(git_post.called)

    @patch.object(utils, 'mkdir')
    @patch.object(utils, 'write_file')
    @patch.object(utils, 'add_user_to_group')
    @patch.object(utils, 'add_group')
    @patch.object(utils, 'adduser')
    def test_git_pre_install(self, adduser, add_group, add_user_to_group,
                             write_file, mkdir):
        utils.git_pre_install()
        adduser.assert_called_with('keystone', shell='/bin/bash',
                                   system_user=True)
        add_group.assert_called_with('keystone', system_group=True)
        add_user_to_group.assert_called_with('keystone', 'keystone')
        expected = [
            call('/var/lib/keystone', owner='keystone',
                 group='keystone', perms=0755, force=False),
            call('/var/lib/keystone/cache', owner='keystone',
                 group='keystone', perms=0755, force=False),
            call('/var/log/keystone', owner='keystone',
                 group='keystone', perms=0755, force=False),
        ]
        self.assertEquals(mkdir.call_args_list, expected)
        write_file.assert_called_with('/var/log/keystone/keystone.log',
                                      '', owner='keystone', group='keystone',
                                      perms=0600)

    @patch.object(utils, 'git_src_dir')
    @patch.object(utils, 'service_restart')
    @patch.object(utils, 'render')
    @patch.object(utils, 'git_pip_venv_dir')
    @patch('os.path.join')
    @patch('os.path.exists')
    @patch('os.symlink')
    @patch('shutil.copytree')
    @patch('shutil.rmtree')
    @patch('subprocess.check_call')
    def test_git_post_install(self, check_call, rmtree, copytree, symlink,
                              exists, join, venv, render, service_restart,
                              git_src_dir):
        projects_yaml = openstack_origin_git
        join.return_value = 'joined-string'
        venv.return_value = '/mnt/openstack-git/venv'
        utils.git_post_install(projects_yaml)
        expected = [
            call('joined-string', '/etc/keystone'),
        ]
        copytree.assert_has_calls(expected)
        expected = [
            call('joined-string', '/usr/local/bin/keystone-manage'),
        ]
        symlink.assert_has_calls(expected, any_order=True)
        keystone_context = {
            'service_description': 'Keystone API server',
            'service_name': 'Keystone',
            'user_name': 'keystone',
            'start_dir': '/var/lib/keystone',
            'process_name': 'keystone',
            'executable_name': 'joined-string',
            'config_files': ['/etc/keystone/keystone.conf'],
            'log_file': '/var/log/keystone/keystone.log',
        }
        expected = [
            call('git/logging.conf', '/etc/keystone/logging.conf', {},
                 perms=0o644),
            call('git.upstart', '/etc/init/keystone.conf',
                 keystone_context, perms=0o644, templates_dir='joined-string'),
        ]
        self.assertEquals(render.call_args_list, expected)
        service_restart.assert_called_with('keystone')

    @patch.object(utils, 'get_manager')
    def test_is_service_present(self, KeystoneManager):
        mock_keystone = MagicMock()
        mock_keystone.resolve_service_id.return_value = 'sid1'
        KeystoneManager.return_value = mock_keystone
        self.assertTrue(utils.is_service_present('bob', 'bill'))

    @patch.object(utils, 'get_manager')
    def test_is_service_present_false(self, KeystoneManager):
        mock_keystone = MagicMock()
        mock_keystone.resolve_service_id.return_value = None
        KeystoneManager.return_value = mock_keystone
        self.assertFalse(utils.is_service_present('bob', 'bill'))

    @patch.object(utils, 'get_manager')
    def test_delete_service_entry(self, KeystoneManager):
        mock_keystone = MagicMock()
        mock_keystone.resolve_service_id.return_value = 'sid1'
        KeystoneManager.return_value = mock_keystone
        utils.delete_service_entry('bob', 'bill')
        mock_keystone.api.services.delete.assert_called_with('sid1')

    @patch('os.path.isfile')
    def test_get_admin_domain_id(self, isfile_mock):
        isfile_mock.return_value = False
        x = utils.get_admin_domain_id()
        assert x is None
        from sys import version_info
        if version_info.major == 2:
            import __builtin__ as builtins
        else:
            import builtins
        from mock import mock_open
        with patch.object(builtins, 'open', mock_open(
                read_data="some_data\n")):
            isfile_mock.return_value = True
            x = utils.get_admin_domain_id()
            self.assertEquals(x, 'some_data')

    def test_assess_status(self):
        with patch.object(utils, 'assess_status_func') as asf:
            callee = MagicMock()
            asf.return_value = callee
            utils.assess_status('test-config')
            asf.assert_called_once_with('test-config')
            callee.assert_called_once_with()

    @patch.object(utils, 'REQUIRED_INTERFACES')
    @patch.object(utils, 'check_optional_relations')
    @patch.object(utils, 'services')
    @patch.object(utils, 'determine_ports')
    @patch.object(utils, 'make_assess_status_func')
    def test_assess_status_func(self,
                                make_assess_status_func,
                                determine_ports,
                                services,
                                check_optional_relations,
                                REQUIRED_INTERFACES):
        services.return_value = 's1'
        determine_ports.return_value = 'p1'
        utils.assess_status_func('test-config')
        make_assess_status_func.assert_called_once_with(
            'test-config', REQUIRED_INTERFACES,
            charm_func=check_optional_relations, services='s1', ports='p1')

    def test_pause_unit_helper(self):
        with patch.object(utils, '_pause_resume_helper') as prh:
            utils.pause_unit_helper('random-config')
            prh.assert_called_once_with(utils.pause_unit, 'random-config')
        with patch.object(utils, '_pause_resume_helper') as prh:
            utils.resume_unit_helper('random-config')
            prh.assert_called_once_with(utils.resume_unit, 'random-config')

    @patch.object(utils, 'services')
    @patch.object(utils, 'determine_ports')
    def test_pause_resume_helper(self, determine_ports, services):
        f = MagicMock()
        services.return_value = 's1'
        determine_ports.return_value = 'p1'
        with patch.object(utils, 'assess_status_func') as asf:
            asf.return_value = 'assessor'
            utils._pause_resume_helper(f, 'some-config')
            asf.assert_called_once_with('some-config')
            f.assert_called_once_with('assessor', services='s1', ports='p1')

    @patch.object(utils, 'run_in_apache')
    @patch.object(utils, 'restart_pid_check')
    def test_restart_function_map(self, restart_pid_check, run_in_apache):
        run_in_apache.return_value = True
        self.assertEqual(utils.restart_function_map(),
                         {'apache2': restart_pid_check})

    @patch.object(utils, 'run_in_apache')
    def test_restart_function_map_legacy(self, run_in_apache):
        run_in_apache.return_value = False
        self.assertEqual(utils.restart_function_map(), {})

    def test_restart_pid_check(self):
        self.subprocess.call.return_value = 1
        utils.restart_pid_check('apache2')
        self.service_stop.assert_called_once_with('apache2')
        self.service_start.assert_called_once_with('apache2')
        self.subprocess.call.assert_called_once_with(['pgrep', 'apache2'])

    def test_restart_pid_check_ptable_string(self):
        self.subprocess.call.return_value = 1
        utils.restart_pid_check('apache2', ptable_string='httpd')
        self.service_stop.assert_called_once_with('apache2')
        self.service_start.assert_called_once_with('apache2')
        self.subprocess.call.assert_called_once_with(['pgrep', 'httpd'])

    def test_restart_pid_check_ptable_string_retry(self):
        call_returns = [1, 0, 0]
        self.subprocess.call.side_effect = lambda x: call_returns.pop()
        utils.restart_pid_check('apache2', ptable_string='httpd')
        self.service_stop.assert_called_once_with('apache2')
        self.service_start.assert_called_once_with('apache2')
#        self.subprocess.call.assert_called_once_with(['pgrep', 'httpd'])
        expected = [
            call(['pgrep', 'httpd']),
            call(['pgrep', 'httpd']),
            call(['pgrep', 'httpd']),
        ]
        self.assertEquals(self.subprocess.call.call_args_list, expected)
