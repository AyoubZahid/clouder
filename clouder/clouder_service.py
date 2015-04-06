# -*- coding: utf-8 -*-
##############################################################################
#
# Author: Yannick Buron
# Copyright 2015, TODAY Clouder SASU
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License with Attribution
# clause as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License with
# Attribution clause along with this program. If not, see
# <http://www.gnu.org/licenses/>.
#
##############################################################################


from openerp import models, fields, api, _
from openerp.exceptions import except_orm
import re

import clouder_model


class ClouderService(models.Model):
    """
    Define the service object, which represent all instances of the application
    installed inside the same container.

    Services use application versions, stored in an archive container, to
    easily switch between versions.
    """

    _name = 'clouder.service'
    _inherit = ['clouder.model']

    def name_get(self, cr, uid, ids, context=None):
        """
        Add the container name to the service name.

        :param cr:
        :param uid:
        :param ids:
        :param context:
        """
        res = []
        for service in self.browse(cr, uid, ids, context=context):
            res.append((service.id, service.name + ' [' +
                        service.container_id.name + '_' +
                        service.container_id.server_id.name + ']'))
        return res

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """
        Modify the search method so we can find a service
        with the container name.

        :param name:
        :param args:
        :param operator:
        :param limit:
        """
        if not args:
            args = []
        if name:
            ids = self.search(
                ['|', ('name', 'like', name),
                 '|', ('container_id.name', 'like', name),
                 ('container_id.server_id.name', 'like', name)] + args,
                limit=limit)
        else:
            ids = self.search(args, limit=limit)
        result = ids.name_get()
        return result

    name = fields.Char('Name', size=64, required=True)
    application_id = fields.Many2one(
        'clouder.application', 'Application',
        related='container_id.application_id', readonly=True)
    application_version_id = fields.Many2one(
        'clouder.application.version', 'Version',
        domain="[('application_id.container_ids','in',container_id)]",
        required=True)
    database_password = fields.Char(
        'Database password', size=64, required=True,
        default=clouder_model.generate_random_password(20))
    container_id = fields.Many2one(
        'clouder.container', 'Container', required=True)
    skip_analytics = fields.Boolean('Skip Analytics?')
    option_ids = fields.One2many(
        'clouder.service.option', 'service_id', 'Options')
    link_ids = fields.One2many(
        'clouder.service.link', 'service_id', 'Links')
    base_ids = fields.One2many('clouder.base', 'service_id', 'Bases')
    parent_id = fields.Many2one('clouder.service', 'Parent Service')
    sub_service_name = fields.Char('Subservice Name', size=64)
    custom_version = fields.Boolean('Custom Version?')
    public = fields.Boolean('Public?')
    partner_id = fields.Many2one(
        'res.partner', 'Manager',
        default=lambda self: self.user_partner)
    partner_ids = fields.Many2many(
        'res.partner', 'clouder_service_partner_rel',
        'service_id', 'partner_id', 'Users')

    @property
    def fullname(self):
        """
        Property returning the full name of the service.
        """
        return self.container_id.name + '-' + self.name

    @property
    def full_localpath(self):
        """
        Property returning the full path of the service instance
        in the destination container.
        """
        return self.container_id.application_id.type_id.localpath_services + \
            '/' + self.name

    @property
    def full_localpath_files(self):
        """
        Property returning the full path of the service files
        in the destination container.
        """
        return self.full_localpath + '/files'

    @property
    def database(self):
        """
        Property returning the database container connected to the service.
        """
        database = False
        for link in self.link_ids:
            if link.target:
                if link.name.name.code in ['postgres', 'mysql']:
                    database = link.target
        return database

    @property
    def database_type(self):
        """
        Property returning the database type connected to the service.
        """
        database_type = self.database.application_id.type_id.name
        if database_type == 'postgres':
            database_type = 'pgsql'
        return database_type

    @property
    def database_server(self):
        """
        Property returning the database server connected to the service.
        """
        if self.database.server_id == self.container_id.server_id:
            return self.database.application_id.code
        else:
            return self.database.server_id.name

    @property
    def db_user(self):
        """
        Property returning the database user of the service.
        """
        db_user = self.fullname.replace('-', '_')
        if self.database_type == 'mysql':
            db_user = self.container_id.name[:10] + '_' + self.name[:4]
            db_user = db_user.replace('-', '_')
        return db_user

    @property
    def port(self):
        """
        Property returning the main port of the service, if existing.
        """
        if 'port' in self.options:
            return self.container_id.ports[
                self.options['port']['value']
            ]
        return False

    @property
    def options(self):
        """
        Property returning a dictionary containing the value of all options
        for this service, even is they are not defined here.
        """
        options = {}
        for option in self.container_id.application_id.type_id.option_ids:
            if option.type == 'service':
                options[option.name] = {
                    'id': option.id, 'name': option.id,
                    'value': option.default}
        for option in self.option_ids:
            options[option.name.name] = {
                'id': option.id, 'name': option.name.id,
                'value': option.value}

        return options

    _sql_constraints = [
        ('name_uniq', 'unique(container_id,name)',
         'Name must be unique per container!'),
    ]

    @api.one
    @api.constrains('name', 'sub_service_name')
    def _validate_data(self):
        """
        Check that the service name does not contain any forbidden
        characters.
        """
        if not re.match("^[\w\d_]*$", self.name):
            raise except_orm(
                _('Data error!'),
                _("Name can only contains letters, digits and underscore "))
        if self.sub_service_name \
                and not re.match("^[\w\d_]*$", self.sub_service_name):
            raise except_orm(
                _('Data error!'),
                _("Sub service name can only contains letters, "
                  "digits and underscore "))

    @api.one
    @api.constrains('application_id', 'application_version_id')
    def _check_application_version(self):
        """
        Check that the application of the application version is the same
        than the application of service.
        """
        if self.application_id and self.application_id.id != \
                self.application_version_id.application_id.id:
            raise except_orm(
                _('Data error!'),
                _("The application of application version must "
                  "be the same than the application of service."))

    @api.one
    @api.constrains('link_ids')
    def _check_database(self):
        """
        Check that a link to a database container is specified.
        """
        if not self.database:
            raise except_orm(
                _('Data error!'),
                _("You need to specify a database in the links "
                  "of the service " + self.name + " " +
                  self.container_id.fullname))

    @api.one
    @api.constrains('option_ids')
    def _check_option_ids(self):
        """
        Check that the required options are filled.
        """
        for type_option in self.application_id.type_id.option_ids:
            if type_option.type == 'service' and type_option.required:
                test = False
                for option in self.option_ids:
                    if option.name == type_option and option.value:
                        test = True
                if not test:
                    raise except_orm(
                        _('Data error!'),
                        _("You need to specify a value for the option " +
                          type_option.name + " for the service " +
                          self.name + "."))

    @api.one
    @api.constrains('link_ids')
    def _check_link_ids(self):
        """
        Check that the required links are specified.
        """
        for app_link in self.application_id.link_ids:
            if app_link.service and app_link.required:
                test = False
                for link in self.link_ids:
                    if link.name == app_link and link.target:
                        test = True
                if not test:
                    raise except_orm(
                        _('Data error!'),
                        _("You need to specify a link to " +
                          app_link.name + " for the service " + self.name))

    @api.multi
    @api.onchange('container_id')
    def onchange_container_id(self):
        """
        Update the options, links and some other fields when we change
        the container_id field.
        """
        if self.container_id:

            options = []
            for type_option\
                    in self.container_id.application_id.type_id.option_ids:
                if type_option.type == 'service' and type_option.auto:
                    test = False
                    for option in self.option_ids:
                        if option.name == type_option:
                            test = True
                    if not test:
                        options.append((0, 0, {'name': type_option,
                                               'value': type_option.default}))
            self.option_ids = options

            links = []
            for app_link in self.container_id.application_id.link_ids:
                if app_link.service and app_link.auto:
                    test = False
                    for link in self.link_ids:
                        if link.name == app_link:
                            test = True
                    if not test:
                        links.append((0, 0, {'name': app_link,
                                             'target': app_link.next}))
            self.link_ids = links

    @api.multi
    def write(self, vals):
        """
        Override write method to redeploy files
        if some key fields have changed.

        :param vals: The values we need to update.
        """
        res = super(ClouderService, self).write(vals)
        if 'application_version_id' in vals:
            self.check_files()
        if 'application_version_id' in vals or 'custom_version' in vals:
            self.deploy_files()
        return res

    @api.one
    def unlink(self):
        """
        Override unlink to remove bases when we unlink a service.
        """
        self.base_ids and self.base_ids.unlink()
        return super(ClouderService, self).unlink()

    @api.multi
    def install_formation(self):
        """
        Create a subservice named formation.
        """
        self.sub_service_name = 'formation'
        self.install_subservice()

    @api.multi
    def install_test(self):
        """
        Create a subservice named test.
        """
        self.sub_service_name = 'test'
        self.install_subservice()

    @api.multi
    def install_subservice(self):
        """
        Create a subservice and duplicate the bases
        linked to the parent service.
        """
        if not self.sub_service_name or self.sub_service_name == self.name:
            return
        services = self.search([('name', '=', self.sub_service_name),
                                ('container_id', '=', self.container_id.id)])
        services.unlink()
        options = []
        type_ids = self.env['clouder.application.type.option'].search(
            [('apptype_id', '=', self.container_id.application_id.type_id.id),
             ('name', '=', 'port')])
        if type_ids:
            if self.sub_service_name == 'formation':
                options = [(0, 0, {'name': type_ids[0].id,
                                   'value': 'port-formation'})]
            if self.sub_service_name == 'test':
                options = [(0, 0, {'name': type_ids[0].id,
                                   'value': 'port-test'})]
        links = []
        for link in self.link_ids:
            links.append((0, 0, {
                'name': link.name.id,
                'target': link.target and link.target.id or False
            }))
        service_vals = {
            'name': self.sub_service_name,
            'container_id': self.container_id.id,
            'application_version_id': self.application_version_id.id,
            'parent_id': self.id,
            'option_ids': options,
            'link_ids': links
        }
        subservice = self.create(service_vals)
        for base in self.base_ids:
            subbase_name = self.sub_service_name + '-' + base.name
            self = self.with_context(
                save_comment='Duplicate base into ' + subbase_name)
            base.reset_base(subbase_name, service_id=subservice)
        self.sub_service_name = False

    @api.multi
    def deploy_to_parent(self):
        """
        Update the parent service with the files of the child service.
        """
        if not self.parent_id:
            return
        vals = {}
        if not self.parent_id.custom_version:
            vals['application_version_id'] = self.application_version_id.id
        else:
            self = self.with_context(files_from_service=self.name)
            vals['custom_version'] = True
        self.parent_id.write(vals)

    @api.multi
    def deploy_post_service(self):
        """
        Hook which can be called by submodules to execute commands after we
        deployed a service.
        """
        return

    @api.multi
    def deploy(self):
        """
        Deploy the service.
        """
        self.purge()

        self.log('Creating database user')

        # SI postgres, create user
        if self.database_type != 'mysql':
            ssh = self.connect(
                self.database.fullname, username='postgres')
            self.execute(ssh, [
                'psql', '-c', '"CREATE USER ' + self.db_user +
                ' WITH PASSWORD \'' + self.database_password + '\' CREATEDB;"'
            ])
            ssh.close()

            ssh = self.connect(
                self.container_id.fullname,
                username=self.container_id.application_id.type_id.system_user)
            self.execute(ssh, [
                'sed', '-i', '"/:*:' + self.db_user + ':/d" ~/.pgpass'])
            self.execute(ssh, [
                'echo "' + self.database_server + ':5432:*:' +
                self.db_user + ':' + self.database_password +
                '" >> ~/.pgpass'])
            self.execute(ssh, ['chmod', '700', '~/.pgpass'])
            ssh.close()

        else:
            ssh = self.connect(self.database.fullname)
            self.execute(ssh, [
                "mysql -u root -p'" + self.database.root_password +
                "' -se \"create user '" + self.db_user +
                "' identified by '" + self.database_password + "';\""])
            ssh.close()

        self.log('Database user created')

        ssh = self.connect(
            self.container_id.fullname,
            username=self.container_id.application_id.type_id.system_user)
        self.execute(ssh, ['mkdir', '-p', self.full_localpath])
        ssh.close()

        self.deploy_files()
        self.deploy_post_service()

        self.container_id.start()

    @api.multi
    def purge_pre_service(self):
        """
        Hook which can be called by submodules to execute commands before we
        purge a service.
        """
        return

    @api.multi
    def purge(self):
        """
        Purge the service.
        """
        self.purge_files()
        self.purge_pre_service()

        ssh = self.connect(
            self.container_id.fullname,
            username=self.container_id.application_id.type_id.system_user)
        self.execute(ssh, ['rm', '-rf', self.full_localpath])
        ssh.close()

        if self.database_type != 'mysql':
            ssh = self.connect(
                self.database.fullname, username='postgres')
            self.execute(ssh, [
                'psql', '-c', '"DROP USER ' + self.db_user + ';"'])
            ssh.close()

            ssh = self.connect(
                self.container_id.fullname,
                username=self.application_id.type_id.system_user)
            self.execute(ssh, [
                'sed', '-i', '"/:*:' + self.db_user + ':/d" ~/.pgpass'])
            ssh.close()

        else:
            ssh = self.connect(self.database.fullname)
            self.execute(ssh, [
                "mysql -u root -p'" + self.database.root_password +
                "' -se \"drop user " + self.db_user + ";\""])
            ssh.close()

        return

    @api.multi
    def check_files(self):
        """
        Check if the files are still used in a container of the specified
        server. If not, the files are removes from the server.
        """
        services = self.search([
            ('application_version_id', '=', self.application_version_id.id),
            ('container_id.server_id', '=', self.container_id.server_id.id)])
        test = False
        for service in services:
            if service.id != self.id:
                test = True
        if not test:
            ssh = self.connect(self.container_id.server_id.name)
            self.execute(ssh, [
                'rm', '-rf', self.application_version_id.full_hostpath])
            ssh.close()

    @api.multi
    def deploy_files(self):
        """
        If not already on the server, the files of the application version are
        copied from the archive container to the server.
        If custom install, the files are copied inside the destination
        container.
        """
        self.purge_files()
        ssh = self.connect(self.container_id.server_id.name)

        if not self.exist(ssh, self.application_version_id.full_hostpath):
            ssh_archive = self.connect(
                self.application_version_id.archive_id.fullname)
            tmp = '/tmp/' + self.application_version_id.fullname + '.tar.gz'

            self.get(ssh_archive,
                     self.application_version_id.full_archivepath_targz, tmp)
            ssh_archive.close()
            self.execute(ssh, [
                'mkdir', '-p', self.application_version_id.full_hostpath])

            self.send(ssh, tmp,
                      self.application_version_id.full_hostpath + '.tar.gz')
            self.execute(ssh, [
                'tar', '-xf',
                self.application_version_id.full_hostpath + '.tar.gz',
                '-C', self.application_version_id.full_hostpath])
            self.execute(ssh, [
                'rm', self.container_id.application_id.full_hostpath + '/' +
                self.application_version_id.name + '.tar.gz'])

        ssh.close()

        ssh = self.connect(
            self.container_id.fullname,
            username=self.container_id.application_id.type_id.system_user)
        if 'files_from_service' in self.env.context:
            self.execute(ssh, [
                'cp', '-R',
                self.container_id.application_id.type_id.localpath_services +
                '/' + self.env.context['files_from_service'] + '/files',
                self.full_localpath_files])
        elif self.custom_version \
                or not self.container_id.application_id.type_id.symlink:
            self.execute(ssh, [
                'cp', '-R', self.application_version_id.full_localpath,
                self.full_localpath_files])
        else:
            self.execute(ssh, [
                'ln', '-s', self.application_version_id.full_localpath,
                self.full_localpath_files])

        for base in self.base_ids:
            base.save()
            base.update_base()
        ssh.close()

    @api.multi
    def purge_files(self):
        """
        Remove files from destination container.
        """
        ssh = self.connect(
            self.container_id.fullname,
            username=self.application_id.type_id.system_user)
        self.execute(ssh, ['rm', '-rf', self.full_localpath_files])
        ssh.close()
        self.check_files()


class ClouderServiceOption(models.Model):
    """
    Define the service.option object, used to define custom values specific
    to a service.
    """

    _name = 'clouder.service.option'

    service_id = fields.Many2one(
        'clouder.service', 'Service', ondelete="cascade", required=True)
    name = fields.Many2one(
        'clouder.application.type.option', 'Option', required=True)
    value = fields.Text('Value')

    _sql_constraints = [
        ('name_uniq', 'unique(service_id,name)',
         'Option name must be unique per service!'),
    ]

    @api.one
    @api.constrains('service_id')
    def _check_required(self):
        """
        Check that we specify a value for the option
        if this option is required.
        """
        if self.name.required and not self.value:
            raise except_orm(
                _('Data error!'),
                _("You need to specify a value for the option " +
                  self.name.name + " for the service " +
                  self.service_id.name + "."))


class ClouderServiceLink(models.Model):
    """
    Define the service.link object, used to specify the applications linked
    to a service.
    """

    _name = 'clouder.service.link'
    _inherit = ['clouder.model']

    service_id = fields.Many2one(
        'clouder.service', 'Service', ondelete="cascade", required=True)
    name = fields.Many2one(
        'clouder.application.link', 'Application Link', required=True)
    target = fields.Many2one(
        'clouder.container', 'Target')

    @api.one
    @api.constrains('service_id')
    def _check_required(self):
        """
        Check that we specify a value for the link
        if this link is required.
        """
        if self.name.required and not self.target:
            raise except_orm(
                _('Data error!'),
                _("You need to specify a link to " +
                  self.name.application_id.name + " for the service " +
                  self.service_id.name))

    @api.multi
    def deploy_link(self):
        """
        Hook which can be called by submodules to execute commands when we
        deploy a link.
        """
        return

    @api.multi
    def purge_link(self):
        """
        Hook which can be called by submodules to execute commands when we
        purge a link.
        """
        return

    @api.multi
    def control(self):
        """
        Make the control to know if we can launch the deploy/purge.
        """
        if not self.target:
            self.log('The target isnt configured in the link, '
                     'skipping deploy link')
            return False
        if not self.name.service:
            self.log('This application isnt for service, skipping deploy link')
            return False
        return True

    @api.multi
    def deploy_(self):
        """
        Control and call the hook to deploy the link.
        """
        self.purge_()
        self.control() and self.deploy_link()

    @api.multi
    def purge_(self):
        """
        Control and call the hook to purge the link.
        """
        self.control() and self.purge_link()