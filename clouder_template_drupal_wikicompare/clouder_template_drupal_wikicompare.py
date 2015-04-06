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

from openerp import models, api
from openerp import modules


class ClouderApplicationVersion(models.Model):
    """
    Add methods to manage the wikicompare application version specificities.
    """

    _inherit = 'clouder.application.version'

    @api.multi
    def build_application(self):
        """
        Patch some files in the archive.
        """
        super(ClouderApplicationVersion, self).build_application()
        if self.application_id.type_id.name == 'drupal'\
                and self.application_id.code == 'wkc':
            ssh = self.connect(self.archive_id.fullname)
            self.send(ssh, modules.get_module_path(
                'clouder_template_drupal_wikicompare') +
                '/res/wikicompare.script',
                self.full_archivepath + '/wikicompare.script')
            self.send(ssh, modules.get_module_path(
                'clouder_template_drupal_wikicompare') +
                '/res/patch/revisioning_postgres.patch',
                self.full_archivepath + '/revisioning_postgres.patch')
            self.execute(ssh, ['patch', '-p0', '-d', self.full_archivepath +
                               '/sites/all/modules/revisioning/', '<',
                               self.full_archivepath +
                               '/revisioning_postgres.patch'])
            ssh.close()

            #
            # if [[ $name == 'dev' ]]
            # then
            # patch -p0 -d $archive_path/$app/${app}-${name}/archive/sites/all/
            # themes/wikicompare_theme/ < $openerp_path/clouder/clouder/apps/
            # drupal/patch/dev_zen_rebuild_registry.patch
            # fi

        return


class ClouderBase(models.Model):
    """
    Add methods to manage the wikicompare base specificities.
    """

    _inherit = 'clouder.base'

    @api.multi
    def deploy_test(self):
        """
        Deploy the wikicompare test data.
        """
        res = super(ClouderBase, self).deploy_test()
        if self.application_id.type_id.name == 'drupal' \
                and self.application_id.code == 'wkc':
            ssh = self.connect(
                self.service_id.container_id.fullname,
                username=self.application_id.type_id.system_user)
            self.execute(ssh, ['drush', 'vset', '--yes', '--exact',
                               'wikicompare_test_platform', '1'],
                         path=self.service_id.full_localpath_files +
                         '/sites/' + self.fulldomain)
            if self.poweruser_name and self.poweruser_email:
                self.execute(ssh, ['drush',
                                   self.service_id.full_localpath_files +
                                   '/wikicompare.script',
                                   '--user=' + self.poweruser_name,
                                   'deploy_demo'],
                             path=self.service_id.full_localpath_files +
                             '/sites/' + self.fulldomain)
            ssh.close()
        return res


