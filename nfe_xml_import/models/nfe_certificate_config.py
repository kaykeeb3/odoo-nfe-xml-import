# -*- coding: utf-8 -*-
from odoo import models, fields

class NFeCertificateConfig(models.Model):
    _name = 'nfe.certificate.config'
    _description = 'Configuração de Certificado Digital para Conexão SEFAZ'
    # Importante: Remova a linha "_inherit = 'mail.thread'" para evitar o erro.

    name = fields.Char(string="Nome da Configuração", default="Certificado SEFAZ", required=True)
    pfx_file = fields.Binary(string="Arquivo .PFX (Certificado A1)", required=True, attachment=True)
    pfx_filename = fields.Char(string="Nome do Arquivo")
    passphrase = fields.Char(string="Senha do Certificado (Passphrase)", password=True, required=True, help="A senha do seu arquivo .PFX")
    cnpj = fields.Char(string="CNPJ da Empresa", size=14, required=True, help="CNPJ que está no Certificado Digital.")
    is_default = fields.Boolean(string="Padrão", help="Marque se esta for a configuração de certificado principal a ser usada.")

    # Campo CUF completo para referência
    cuf_autor = fields.Selection(
        [
            ('11', '11 - Rondônia'), ('12', '12 - Acre'), ('13', '13 - Amazonas'), ('14', '14 - Roraima'),
            ('15', '15 - Pará'), ('16', '16 - Amapá'), ('17', '17 - Tocantins'), ('21', '21 - Maranhão'),
            ('22', '22 - Piauí'), ('23', '23 - Ceará'), ('24', '24 - Rio Grande do Norte'), ('25', '25 - Paraíba'),
            ('26', '26 - Pernambuco'), ('27', '27 - Alagoas'), ('28', '28 - Sergipe'), ('29', '29 - Bahia'),
            ('31', '31 - Minas Gerais'), ('32', '32 - Espírito Santo'), ('33', '33 - Rio de Janeiro'),
            ('35', '35 - São Paulo'), ('41', '41 - Paraná'), ('42', '42 - Santa Catarina'),
            ('43', '43 - Rio Grande do Sul'), ('50', '50 - Mato Grosso do Sul'), ('51', '51 - Mato Grosso'),
            ('52', '52 - Goiás'), ('53', '53 - Distrito Federal'),
        ],
        string="UF Autorizadora (Estado)", required=True
    )

    # Método para o botão 'toggle_is_default' (necessário para a view funcionar)
    def toggle_is_default(self):
        """ Alterna o status 'Padrão' e garante que apenas um certificado seja padrão. """
        self.ensure_one()

        if not self.is_default:
            # Desmarca todos os outros antes de marcar este
            self.search([('is_default', '=', True)]).write({'is_default': False})

        self.is_default = not self.is_default
        return True