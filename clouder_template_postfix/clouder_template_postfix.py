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


class ClouderContainer(models.Model):
    """
    Add methods to manage the postfix specificities.
    """

    _inherit = 'clouder.container'

    @api.multi
    def deploy_post(self):
        """
        Add a ssmtp file if the container is linked to a postfix, and the
        configure the postfix.
        """
        super(ClouderContainer, self).deploy_post()

        for link in self.link_ids:
            if link.name.name.code == 'postfix' and link.target:
                ssh = self.connect(self.fullname)
                self.execute(ssh, ['echo "root=' + self.email_sysadmin +
                                   '" > /etc/ssmtp/ssmtp.conf'])
                self.execute(ssh, ['echo "mailhub=postfix:25" '
                                   '>> /etc/ssmtp/ssmtp.conf'])
                self.execute(ssh, ['echo "rewriteDomain=' + self.fullname +
                                   '" >> /etc/ssmtp/ssmtp.conf'])
                self.execute(ssh, ['echo "hostname=' + self.fullname +
                                   '" >> /etc/ssmtp/ssmtp.conf'])
                self.execute(ssh, ['echo "FromLineOverride=YES" >> '
                                   '/etc/ssmtp/ssmtp.conf'])
                ssh.close()

        if self.application_id.type_id.name == 'postfix':
            ssh = self.connect(self.fullname)
            self.execute(ssh, [
                'echo "relayhost = [smtp.mandrillapp.com]" '
                '>> /etc/postfix/main.cf'])
            self.execute(ssh, [
                'echo "smtp_sasl_auth_enable = yes" >> /etc/postfix/main.cf'])
            self.execute(ssh, [
                'echo "smtp_sasl_password_maps = '
                'hash:/etc/postfix/sasl_passwd" >> /etc/postfix/main.cf'])
            self.execute(ssh, [
                'echo "smtp_sasl_security_options = noanonymous" '
                '>> /etc/postfix/main.cf'])
            self.execute(ssh,
                         ['echo "smtp_use_tls = yes" >> /etc/postfix/main.cf'])
            self.execute(ssh, [
                'echo "mynetworks = 127.0.0.0/8 172.17.0.0/16" '
                '>> /etc/postfix/main.cf'])
            self.execute(ssh, [
                'echo "[smtp.mandrillapp.com]    ' +
                self.options['mailchimp_username']['value'] + ':' +
                self.options['mailchimp_apikey']['value'] +
                '" > /etc/postfix/sasl_passwd'])
            self.execute(ssh, ['postmap /etc/postfix/sasl_passwd'])

            self.send(ssh,
                      modules.get_module_path('clouder_template_postfix') +
                      '/res/openerp_mailgate.py',
                      '/bin/openerp_mailgate.py')

            self.execute(ssh, ['chmod', '+x', '/bin/openerp_mailgate.py'])
            ssh.close()