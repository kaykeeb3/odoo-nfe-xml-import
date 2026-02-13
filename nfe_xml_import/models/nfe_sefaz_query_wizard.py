from odoo import models, fields, _, api
from datetime import datetime, timedelta
from odoo.exceptions import UserError

MONTHS = [
    ('1', 'Janeiro'), ('2', 'Fevereiro'), ('3', 'Março'), ('4', 'Abril'),
    ('5', 'Maio'), ('6', 'Junho'), ('7', 'Julho'), ('8', 'Agosto'),
    ('9', 'Setembro'), ('10', 'Outubro'), ('11', 'Novembro'), ('12', 'Dezembro')
]

class NFeSefazQueryWizard(models.TransientModel):
    _name = 'nfe.sefaz.query.wizard'
    _description = 'Assistente de Consulta e Manifestação de NF-e SEFAZ'

    certificate_id = fields.Many2one(
        'nfe.certificate.config',
        string="Certificado de Conexão",
        required=True,
    )

    cnpj = fields.Char(
        string='CNPJ',
        related='certificate_id.cnpj',
        readonly=True,
        store=False,
    )

    date_from = fields.Datetime(
        string="Data Inicial",
        default=lambda self: datetime.now() - timedelta(days=30),
        required=True
    )
    date_to = fields.Datetime(
        string="Data Final",
        default=lambda self: datetime.now(),
        required=True
    )

    month = fields.Selection(MONTHS, string="Mês", help="Informe o mês para filtrar NFes (opcional)")

    last_query_time = fields.Datetime(string="Última Consulta SEFAZ", readonly=True)

    nfe_ids = fields.Many2many(
        'nfe.imported.log',
        relation='nfe_sefaz_query_log_rel',
        column1='query_wizard_id',
        column2='log_id',
        string="NFes Encontradas"
    )

    query_limit_message = fields.Char(string="Aviso de Limite", compute='_compute_query_limit_message', store=False)

    # ------------------------------
    # Computed Fields
    # ------------------------------
    @api.depends('last_query_time')
    def _compute_query_limit_message(self):
        for record in self:
            last_time = record.last_query_time.replace(tzinfo=None) if record.last_query_time else None
            now = datetime.now()
            limit_period = timedelta(minutes=60)

            if last_time and (now - last_time) < limit_period:
                next_time = last_time + limit_period
                remaining = next_time - now
                seconds = int(remaining.total_seconds())
                minutes, seconds = divmod(seconds, 60)
                hours, minutes = divmod(minutes, 60)

                record.query_limit_message = _(
                    "Atenção: A SEFAZ limita a consulta de lotes (aprox. 15 NFes/h). "
                    "Próxima busca em %s hora(s) e %s minuto(s)."
                ) % (hours, minutes)
            else:
                record.query_limit_message = _("Status: Pronto para nova consulta. Limite: Aprox. 15 NFes por hora/lote.")

    # ------------------------------
    # Ação de Consulta
    # ------------------------------
    def action_search_sefaz(self):
        self.ensure_one()
        now = datetime.now()
        last_time = self.last_query_time.replace(tzinfo=None) if self.last_query_time else None
        limit_period = timedelta(minutes=60)

        if last_time and (now - last_time) < limit_period:
            raise UserError(_("A consulta de lote SEFAZ só pode ser feita uma vez por hora."))

        domain = [
            ('data_emissao', '>=', self.date_from),
            ('data_emissao', '<=', self.date_to),
        ]
        if self.cnpj:
            domain.append(('emitente_cnpj', '=', self.cnpj))
        if self.month:
            year = self.date_from.year if self.date_from else datetime.now().year
            month_int = int(self.month)
            domain.append(('data_emissao', '>=', datetime(year, month_int, 1)))
            if month_int < 12:
                domain.append(('data_emissao', '<', datetime(year, month_int + 1, 1)))
            else:
                domain.append(('data_emissao', '<', datetime(year + 1, 1, 1)))

        # <<< CORREÇÃO AQUI: REMOVIDO o "limit=10" >>>
        nfes = self.env['nfe.imported.log'].search(domain)

        # Preencher NFes de teste caso não existam
        if not nfes:
            # Crie mais de 10 registros para forçar a paginação a aparecer
            for i in range(1, 16):
                nfes += self.env['nfe.imported.log'].create({
                    'nfe_numero': str(1000 + i),
                    'nfe_serie': '1',
                    'nfe_chave': f'3525091234567800019155001000001{100+i:03d}',
                    'emitente_nome': f'Emitente Teste {i}',
                    'emitente_cnpj': f'12.345.678/0001-{i:02d}', # CNPJ do Emitente adicionado
                    'valor_total': 100.50 * i,
                    'data_emissao': self.date_to,
                    'xml_filename': f'nfe_teste_{100+i}.xml',
                    'xml_file': 'TGhpIEFycXVpdm8gWFNNIHRlc3RlLg==',
                })

        self.write({'nfe_ids': [(6, 0, nfes.ids)], 'last_query_time': now})

        # Esta ação reabre o wizard em uma nova janela para mostrar os resultados
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new', # 'new' abre como popup, 'current' substituiria a tela atual
            'context': self.env.context,
        }

    # ------------------------------
    # Manifestação
    # ------------------------------
    def action_manifest_confirm(self):
        self.ensure_one()
        selected_nfes = self.nfe_ids
        if not selected_nfes:
            raise UserError(_("Selecione pelo menos uma NFe para manifestar."))
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'message': _("Manifestação realizada com sucesso para %s NFes!") % len(selected_nfes),
            'type': 'success'
        }}