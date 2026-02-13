# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import xml.etree.ElementTree as ET
import csv
import io
import logging
from datetime import datetime
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class NFeImport(models.Model):
    _name = "nfe.import"
    _description = "Importação de Nota Fiscal XML"

    def _get_valid_product_type(self):
        ProductTemplate = self.env['product.template']
        if 'detailed_type' in ProductTemplate._fields:
            fd = ProductTemplate.fields_get(['detailed_type'])['detailed_type']
            options = [opt[0] for opt in fd.get('selection') or []]
            for candidate in ('product', 'storable', 'stockable', 'stockable_product'):
                if candidate in options:
                    return 'detailed_type', candidate
            if options:
                return 'detailed_type', options[0]
        if 'type' in ProductTemplate._fields:
            fd = ProductTemplate.fields_get(['type'])['type']
            options = [opt[0] for opt in fd.get('selection') or []]
            for candidate in ('product', 'storable', 'stockable'):
                if candidate in options:
                    return 'type', candidate
            if options:
                return 'type', options[0]
        return None, None

class NFeImportedLog(models.Model):
    _name = 'nfe.imported.log'
    _description = 'Log de NFes Importadas'
    _rec_name = 'nfe_numero'

    nfe_numero = fields.Char('Número da NFe', required=True, index=True)
    nfe_serie = fields.Char('Série da NFe', required=True)
    nfe_chave = fields.Char('Chave de Acesso', required=True, index=True)
    emitente_cnpj = fields.Char('CNPJ do Emitente')
    emitente_nome = fields.Char('Nome do Emitente')
    data_emissao = fields.Date('Data de Emissão')
    data_importacao = fields.Datetime('Data de Importação', default=fields.Datetime.now)
    usuario_importacao = fields.Many2one('res.users', 'Usuário', default=lambda self: self.env.user)
    valor_total = fields.Float('Valor Total')
    xml_filename = fields.Char('Nome do Arquivo XML')
    xml_file = fields.Binary('Arquivo XML', attachment=True, readonly=True)

    # Novos campos para o endereço do emitente
    emitente_logradouro = fields.Char('Logradouro do Emitente')
    emitente_numero_end = fields.Char('Número do Endereço')
    emitente_bairro = fields.Char('Bairro do Emitente')
    emitente_municipio = fields.Char('Município do Emitente')
    emitente_uf = fields.Char('UF do Emitente')
    emitente_cep = fields.Char('CEP do Emitente')

    # NOVOS CAMPOS ADICIONADOS PARA RESOLVER O ERRO
    status = fields.Selection([
        ('pendente', 'Pendente'),
        ('visualizada', 'Visualizada'),
        ('analisada', 'Analisada'),
    ], string='Status', default='pendente', required=True)
    nfe_tipo = fields.Selection([
        ('entrada', 'Entrada'),
        ('saida', 'Saída'),
    ], string='Tipo', required=True, default='entrada')
    company_id = fields.Many2one('res.company', string='Empresa', required=True, default=lambda self: self.env.company)

    _sql_constraints = [
        ('chave_unica', 'unique(nfe_chave)', 'Esta NFe já foi importada anteriormente!'),
    ]

    def action_download_xml(self):
        """
        Ação para baixar o arquivo XML original.
        """
        self.ensure_one()
        if not self.xml_file:
            raise UserError("Não há arquivo XML para baixar.")

        return {
            'type': 'ir.actions.act_url',
            'url': f'web/content/{self._name}/{self.id}/xml_file/{self.xml_filename}',
            'target': 'self',
        }


class NFeXmlImport(models.TransientModel):
    _name = "nfe.xml.import"
    _description = "Wizard de Importação NFe"

    xml_file = fields.Binary('Arquivo XML NFe', required=True)
    xml_filename = fields.Char(string="Nome do Arquivo XML")
    target_model_id = fields.Many2one('ir.model', string="Modelo de Destino")
    assigned_to = fields.Many2one('res.users', string="Atribuído a")
    scheduled_date = fields.Datetime(string="Data Agendada")

    def _safe_float(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _extract_nfe_info(self, root, ns):
        nfe_info = root.find('.//nfe:infNFe', ns)
        if nfe_info is None:
            raise UserError(_("XML inválido: não foi possível encontrar informações da NFe"))

        chave_acesso = nfe_info.get('Id', '').replace('NFe', '')

        ide = nfe_info.find('nfe:ide', ns)
        nfe_numero = ide.find('nfe:nNF', ns).text if ide is not None and ide.find('nfe:nNF', ns) is not None else ''
        nfe_serie = ide.find('nfe:serie', ns).text if ide is not None and ide.find('nfe:serie', ns) is not None else ''
        data_emissao = ide.find('nfe:dhEmi', ns).text if ide is not None and ide.find('nfe:dhEmi', ns) is not None else ''

        emit = nfe_info.find('nfe:emit', ns)
        emitente_cnpj = emit.find('nfe:CNPJ', ns).text if emit is not None and emit.find('nfe:CNPJ', ns) is not None else ''
        emitente_nome = emit.find('nfe:xNome', ns).text if emit is not None and emit.find('nfe:xNome', ns) is not None else ''

        # Extração dos dados de endereço
        ender_emit = emit.find('nfe:enderEmit', ns)
        emitente_logradouro = ender_emit.find('nfe:xLgr', ns).text if ender_emit is not None and ender_emit.find('nfe:xLgr', ns) is not None else ''
        emitente_numero_end = ender_emit.find('nfe:nro', ns).text if ender_emit is not None and ender_emit.find('nfe:nro', ns) is not None else ''
        emitente_bairro = ender_emit.find('nfe:xBairro', ns).text if ender_emit is not None and ender_emit.find('nfe:xBairro', ns) is not None else ''
        emitente_municipio = ender_emit.find('nfe:xMun', ns).text if ender_emit is not None and ender_emit.find('nfe:xMun', ns) is not None else ''
        emitente_uf = ender_emit.find('nfe:UF', ns).text if ender_emit is not None and ender_emit.find('nfe:UF', ns) is not None else ''
        emitente_cep = ender_emit.find('nfe:CEP', ns).text if ender_emit is not None and ender_emit.find('nfe:CEP', ns) is not None else ''

        total = nfe_info.find('nfe:total/nfe:ICMSTot/nfe:vNF', ns)
        valor_total = self._safe_float(total.text if total is not None else 0.0)

        return {
            'chave_acesso': chave_acesso,
            'numero': nfe_numero,
            'serie': nfe_serie,
            'data_emissao': data_emissao,
            'emitente_cnpj': emitente_cnpj,
            'emitente_nome': emitente_nome,
            'valor_total': valor_total,
            'emitente_logradouro': emitente_logradouro,
            'emitente_numero_end': emitente_numero_end,
            'emitente_bairro': emitente_bairro,
            'emitente_municipio': emitente_municipio,
            'emitente_uf': emitente_uf,
            'emitente_cep': emitente_cep,
        }

    def _check_nfe_already_imported(self, nfe_info):
        if not nfe_info.get('chave_acesso'):
            return False
        return self.env['nfe.imported.log'].search([('nfe_chave', '=', nfe_info['chave_acesso'])], limit=1).exists()

    def _register_nfe_import(self, nfe_info):
        data_emissao = fields.Date.today()
        if nfe_info.get('data_emissao'):
            try:
                dt_emissao = datetime.fromisoformat(nfe_info['data_emissao'].replace('Z', '+00:00'))
                data_emissao = dt_emissao.date()
            except Exception:
                pass

        self.env['nfe.imported.log'].create({
            'nfe_numero': nfe_info.get('numero', ''),
            'nfe_serie': nfe_info.get('serie', ''),
            'nfe_chave': nfe_info.get('chave_acesso', ''),
            'emitente_cnpj': nfe_info.get('emitente_cnpj', ''),
            'emitente_nome': nfe_info.get('emitente_nome', ''),
            'data_emissao': data_emissao,
            'valor_total': nfe_info.get('valor_total', 0.0),
            'xml_filename': self.xml_filename or '',
            'xml_file': self.xml_file,  # Salva o arquivo XML para download futuro
            'emitente_logradouro': nfe_info.get('emitente_logradouro', ''),
            'emitente_numero_end': nfe_info.get('emitente_numero_end', ''),
            'emitente_bairro': nfe_info.get('emitente_bairro', ''),
            'emitente_municipio': nfe_info.get('emitente_municipio', ''),
            'emitente_uf': nfe_info.get('emitente_uf', ''),
            'emitente_cep': nfe_info.get('emitente_cep', ''),
        })

    # ... (métodos _convert_to_csv_data, _create_or_update_products, etc. sem alterações) ...
    def _safe_float(self, value):
        """Converte valor para float de forma segura"""
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _parse_nfe_xml(self, xml_content):
        """
        Analisa o conteúdo XML da NFe e extrai os dados dos produtos
        Retorna uma tupla: (produtos_data, nfe_info)
        """
        try:
            if isinstance(xml_content, bytes):
                xml_content = xml_content.decode('utf-8')

            root = ET.fromstring(xml_content)
            ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

            # Extrai informações da NFe
            nfe_info = self._extract_nfe_info(root, ns)

            if self._check_nfe_already_imported(nfe_info):
                raise UserError(_(
                    "Esta NFe já foi importada anteriormente!\n"
                    "NFe: %s - Série: %s\n"
                    "Emitente: %s"
                ) % (nfe_info.get('numero'), nfe_info.get('serie'), nfe_info.get('emitente_nome')))

            # Registra a NFe no log
            self._register_nfe_import(nfe_info)

            produtos_data = []
            nfe_info_element = root.find('.//nfe:infNFe', ns)
            if nfe_info_element is None:
                raise UserError(_("XML inválido: não encontrou infNFe"))

            detalhes = nfe_info_element.findall('nfe:det', ns)
            data_emissao = nfe_info.get('data_emissao') or fields.Date.today()

            for det in detalhes:
                prod = det.find('nfe:prod', ns)
                if prod is None:
                    _logger.warning("Item 'det' sem 'prod' ignorado.")
                    continue

                codigo_produto = prod.find('nfe:cProd', ns).text if prod.find('nfe:cProd', ns) is not None else None
                nome_produto = prod.find('nfe:xProd', ns).text if prod.find('nfe:xProd', ns) is not None else None

                if not codigo_produto:
                    _logger.warning("Produto sem código interno ignorado: %s", nome_produto or 'Sem nome')
                    continue

                produto_data = {
                    'codigo_produto': codigo_produto,
                    'nome_produto': nome_produto or '',
                    'ncm': prod.find('nfe:NCM', ns).text if prod.find('nfe:NCM', ns) is not None else '',
                    'quantidade': self._safe_float(prod.find('nfe:qCom', ns).text if prod.find('nfe:qCom', ns) is not None else 0.0),
                    'valor_unitario': self._safe_float(prod.find('nfe:vUnCom', ns).text if prod.find('nfe:vUnCom', ns) is not None else 0.0),
                    'valor_total': self._safe_float(prod.find('nfe:vProd', ns).text if prod.find('nfe:vProd', ns) is not None else 0.0),
                    'unidade': prod.find('nfe:uCom', ns).text if prod.find('nfe:uCom', ns) is not None else '',
                    'emitente': nfe_info.get('emitente_nome', ''),
                    'data_emissao': data_emissao,
                    'chave_acesso': nfe_info.get('chave_acesso'),
                }
                produtos_data.append(produto_data)

            return produtos_data, nfe_info

        except ET.ParseError as e:
            raise UserError(_("Erro ao analisar XML: %s") % str(e))
        except Exception as e:
            _logger.error("Erro ao processar XML da NFe: %s", str(e))
            raise


    def _convert_to_csv_data(self, produtos_data):
        """
        Converte os dados dos produtos para formato CSV compatível com Odoo
        """
        if not produtos_data:
            return [], []

        headers = [
            'product_id',
            'prod_lot_id',
            'theoretical_qty',
            'product_qty',
            'difference_qty',
            'date',
            'user_id',
            'product_name',
            'product_code',
            'ncm',
            'unit_of_measure',
        ]

        csv_data = []
        for produto in produtos_data:
            linha = [
                produto.get('nome_produto', ''),
                produto.get('lot_serial_number', ''),
                str(produto.get('quantidade', 0.0)),
                str(produto.get('counted_quantity', 0.0)),
                str(produto.get('difference', 0.0)),
                produto.get('scheduled_date', ''),
                '',
                produto.get('nome_produto', ''),
                produto.get('codigo_produto', ''),
                produto.get('ncm', ''),
                produto.get('unidade', ''),
            ]
            csv_data.append(linha)

        return headers, csv_data

    def _create_or_update_products(self, produtos_data):
        """
        Cria ou atualiza produtos no Odoo baseado nos dados da NFe.
        """
        Product = self.env['product.product']
        product_mapping = {}

        try:
            default_categ = self.env.ref('product.product_category_all')
        except ValueError:
            default_categ = self.env['product.category'].search([], limit=1)
            if not default_categ:
                raise UserError(_("Nenhuma categoria de produto foi encontrada. Por favor, crie uma categoria de produto para continuar."))

        for produto in produtos_data:
            codigo = produto.get('codigo_produto', '').strip()
            nome = produto.get('nome_produto', '').strip()

            if not codigo and not nome:
                continue

            domain = []
            if codigo:
                domain.append(('default_code', '=', codigo))

            if not domain or not Product.search(domain, limit=1):
                domain = [('name', '=', nome)]

            existing_product = Product.search(domain, limit=1)

            if existing_product:
                product_mapping[codigo or nome] = existing_product.id
            else:
                product_vals = {
                    'name': nome or f"Produto {codigo}",
                    'default_code': codigo or None,
                    'type': 'consu',
                    'tracking': 'none',
                    'categ_id': default_categ.id,
                    'list_price': produto.get('valor_unitario', 0.0),
                    'standard_price': produto.get('valor_unitario', 0.0),
                }

                try:
                    new_product = Product.create(product_vals)
                    product_mapping[codigo or nome] = new_product.id
                    _logger.info("Produto criado: %s (ID: %s)", nome, new_product.id)
                except Exception as e:
                    _logger.error("Falha ao criar o produto %s: %s", nome, e)
                    pass

        return product_mapping

    def process_xml_import(self):
        """
        Processa a importação do XML da NFe, cria/atualiza produtos e estoque.
        """
        self.ensure_one()

        if not self.xml_file:
            raise UserError(_("Por favor, selecione um arquivo XML"))

        xml_content = base64.b64decode(self.xml_file)
        produtos_data, nfe_info = self._parse_nfe_xml(xml_content)

        if not produtos_data:
            raise UserError(_("Nenhum produto encontrado no XML da NFe"))

        product_mapping = self._create_or_update_products(produtos_data)

        location = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        if not location:
            raise UserError(_("Localização de estoque padrão não encontrada"))

        created_records = []
        updated_records = []
        messages = []

        for p in produtos_data:
            product_id = product_mapping.get(p['codigo_produto'] or p['nome_produto'])
            if not product_id:
                messages.append({'type': 'warning', 'message': _("Produto não encontrado: %s") % p['nome_produto']})
                continue

            self.env.cr.execute("""
                SELECT id, quantity FROM stock_quant
                WHERE product_id = %s AND location_id = %s
                LIMIT 1
            """, (product_id, location.id))
            result = self.env.cr.fetchone()

            if result:
                quant_id, current_qty = result
                self.env.cr.execute("""
                    UPDATE stock_quant
                    SET quantity = quantity + %s,
                        write_date = NOW()
                    WHERE id = %s
                """, (p['quantidade'], quant_id))
                updated_records.append(quant_id)
                messages.append({'type': 'success', 'message': _("Estoque atualizado para %s (+%s)") % (p['nome_produto'], p['quantidade'])})
            else:
                self.env.cr.execute("""
                    INSERT INTO stock_quant (product_id, location_id, quantity, reserved_quantity, in_date, create_date, write_date)
                    VALUES (%s, %s, %s, %s, NOW(), NOW(), NOW())
                    RETURNING id
                """, (product_id, location.id, p['quantidade'], 0.0))
                new_id = self.env.cr.fetchone()[0]
                created_records.append(new_id)
                messages.append({'type': 'success', 'message': _("Novo estoque criado para %s: %s") % (p['nome_produto'], p['quantidade'])})

        nfe_chave = nfe_info.get('chave_acesso', '').replace('NFe', '').strip()
        _logger.info("NFe importada com sucesso: %s", nfe_chave)

        return {
            'ids': created_records + updated_records,
            'messages': messages,
            'name': _("Importação NFe - %s produtos processados") % len(produtos_data),
            'created_count': len(created_records),
            'updated_count': len(updated_records),
        }

    # ... (métodos _import_to_inventory, _import_to_stock_quant, etc. sem alterações) ...
    def _import_to_inventory(self, headers, csv_data, product_mapping, produtos_data):
        """
        Importa dados para o modelo stock.quant (Inventário de Estoque)
        """
        StockQuant = self.env['stock.quant']

        created_records = []
        updated_records = []
        errors = []

        for i, linha in enumerate(csv_data):
            try:
                codigo_produto = produtos_data[i].get('codigo_produto', '')
                nome_produto = produtos_data[i].get('nome_produto', '')
                quantidade_nfe = produtos_data[i].get('quantidade', 0.0)

                product_id = product_mapping.get(codigo_produto or nome_produto)
                if not product_id:
                    errors.append(f"Produto não encontrado: {nome_produto} ({codigo_produto})")
                    continue

                location = self.env['stock.location'].search([
                    ('usage', '=', 'internal')
                ], limit=1)

                if not location:
                    try:
                        location = self.env.ref('stock.stock_location_stock')
                    except:
                        raise UserError(_("Nenhuma localização de estoque encontrada"))

                existing_quant = StockQuant.search([
                    ('product_id', '=', product_id),
                    ('location_id', '=', location.id),
                ], limit=1)

                if existing_quant:
                    nova_quantidade = existing_quant.quantity + quantidade_nfe
                    existing_quant.write({
                        'quantity': nova_quantidade,
                    })
                    updated_records.append(existing_quant.id)
                    _logger.info("Quantidade atualizada para produto %s: %s -> %s",
                                 nome_produto, existing_quant.quantity - quantidade_nfe, nova_quantidade)
                else:
                    quant_vals = {
                        'product_id': product_id,
                        'location_id': location.id,
                        'quantity': quantidade_nfe,
                    }

                    new_quant = StockQuant.create(quant_vals)
                    created_records.append(new_quant.id)
                    _logger.info("Novo registro de estoque criado para produto %s: %s",
                                 nome_produto, quantidade_nfe)

            except Exception as e:
                errors.append(f"Erro na linha {i+1}: {str(e)}")
                _logger.error("Erro ao processar linha %s: %s", i+1, str(e))

        result = {
            'ids': created_records + updated_records,
            'messages': [],
            'name': [],
            'created_count': len(created_records),
            'updated_count': len(updated_records),
        }

        if errors:
            for error in errors:
                result['messages'].append({
                    'type': 'warning',
                    'message': error,
                    'record': False
                })

        return result

    def _import_to_stock_quant(self, headers, csv_data, product_mapping, produtos_data):
        """
        Importa dados diretamente para stock.quant
        """
        return self._import_to_inventory(headers, csv_data, product_mapping, produtos_data)

    def _show_preview(self, headers, csv_data):
        """
        Mostra preview dos dados extraídos do XML
        """
        return {
            'headers': headers,
            'preview': csv_data[:10],
            'total_rows': len(csv_data),
        }

    def _get_or_create_lot(self, lot_name, product_id):
        """
        Busca ou cria um lote/série para o produto
        """
        if not lot_name:
            return False

        ProductionLot = self.env['stock.lot']

        existing_lot = ProductionLot.search([
            ('name', '=', lot_name),
            ('product_id', '=', product_id)
        ], limit=1)

        if existing_lot:
            return existing_lot.id

        new_lot = ProductionLot.create({
            'name': lot_name,
            'product_id': product_id,
        })

        return new_lot.id

    @api.model
    def _read_xml_nfe(self, options):
        """
        Método específico para ler arquivos XML de NFe
        """
        if not self.xml_file:
            raise UserError(_("Nenhum arquivo XML selecionado"))

        try:
            xml_content = base64.b64decode(self.xml_file)
            produtos_data = self._parse_nfe_xml(xml_content)
            headers, csv_data = self._convert_to_csv_data(produtos_data)
            return len(csv_data), [headers] + csv_data

        except Exception as e:
            _logger.error("Erro ao ler arquivo XML NFe: %s", str(e))
            raise UserError(_("Erro ao ler arquivo XML: %s") % str(e))

class StockQuantInherit(models.Model):
    """
    Estende stock.quant para melhor integração com importação NFe
    """
    _inherit = 'stock.quant'

    nfe_reference = fields.Char('Referência NFe', help="Referência da Nota Fiscal de origem")
    import_date = fields.Datetime('Data de Importação', default=fields.Datetime.now)

class BaseImportExtended(models.TransientModel):
    _inherit = 'base_import.import'

    @api.model
    def _read_file(self, options):
        """
        Estende o método _read_file para suportar arquivos XML de NFe
        """
        if self.file_type == 'application/xml' or (self.file_name and self.file_name.lower().endswith('.xml')):
            try:
                xml_content = self.file or b''
                if b'nfeProc' in xml_content or b'NFe' in xml_content:
                    return self._read_xml_nfe(options)
            except:
                pass

        return super()._read_file(options)

    def _read_xml_nfe(self, options):
        """
        Processa arquivo XML de NFe e converte para formato de importação
        """
        try:
            xml_content = self.file or b''
            root = ET.fromstring(xml_content)
            ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

            headers = [
                'name',
                'default_code',
                'list_price',
                'standard_price',
                'qty_available',
                'uom_id/name',
            ]

            rows = [headers]

            nfe_info = root.find('.//nfe:infNFe', ns)
            if nfe_info is not None:
                detalhes = nfe_info.findall('nfe:det', ns)

                for det in detalhes:
                    prod = det.find('nfe:prod', ns)
                    if prod is None:
                        continue

                    nome = prod.find('nfe:xProd', ns).text if prod.find('nfe:xProd', ns) is not None else ''
                    codigo = prod.find('nfe:cProd', ns).text if prod.find('nfe:cProd', ns) is not None else ''
                    valor_unit = prod.find('nfe:vUnCom', ns).text if prod.find('nfe:vUnCom', ns) is not None else '0'
                    quantidade = prod.find('nfe:qCom', ns).text if prod.find('nfe:qCom', ns) is not None else '0'
                    unidade = prod.find('nfe:uCom', ns).text if prod.find('nfe:uCom', ns) is not None else 'un'

                    linha_dados = [
                        nome,
                        codigo,
                        valor_unit,
                        valor_unit,
                        quantidade,
                        unidade,
                    ]

                    rows.append(linha_dados)

            return len(rows) - 1, rows

        except Exception as e:
            _logger.error("Erro ao processar XML NFe: %s", str(e))
            raise UserError(_("Erro ao processar arquivo XML: %s") % str(e))

class NFeImportWizard(models.TransientModel):
    """
    Wizard simplificado para importação de XMLs de NFe
    """
    _name = 'nfe.import.wizard'
    _description = 'Assistente de Importação NFe'

    xml_file = fields.Binary('Arquivo XML NFe', required=True)
    xml_filename = fields.Char('Nome do Arquivo')

    import_type = fields.Selection([
        ('products', 'Importar apenas Produtos'),
        ('inventory', 'Importar para Inventário'),
        ('both', 'Importar Produtos e Inventário'),
    ], string='Tipo de Importação', default='both', required=True)

    location_id = fields.Many2one('stock.location', string='Localização de Estoque',
                                 domain=[('usage', '=', 'internal')],
                                 default=lambda self: self.env.ref('stock.stock_location_stock', raise_if_not_found=False))

    assigned_to = fields.Many2one('res.users', string='Responsável',
                                 default=lambda self: self.env.user)

    def action_import_nfe(self):
        """
        Ação principal para importar dados da NFe
        """
        self.ensure_one()

        if not self.xml_file:
            raise UserError(_("Por favor, selecione um arquivo XML"))

        target_model = self.env['ir.model'].search([
            ('model', '=', 'stock.inventory' if self.import_type in ['inventory', 'both'] else 'product.product')
        ], limit=1)

        import_record = self.env['nfe.xml.import'].create({
            'xml_file': self.xml_file,
            'xml_filename': self.xml_filename,
            'target_model_id': target_model.id,
            'assigned_to': self.assigned_to.id,
            'scheduled_date': fields.Date.today(),
        })

        try:
            result = import_record.process_xml_import()

            message = _("Importação concluída com sucesso!\n")
            if result.get('created_count', 0) > 0:
                message += _("Novos registros criados: %s\n") % result['created_count']
            if result.get('updated_count', 0) > 0:
                message += _("Registros atualizados: %s\n") % result['updated_count']

            if result.get('messages'):
                message += _("\nAvisos:\n")
                for msg in result['messages'][:5]:
                    message += f"- {msg['message']}\n"
                if len(result['messages']) > 5:
                    message += f"... e mais {len(result['messages']) - 5} avisos.\n"

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Resultado da Importação"),
                    'message': message,
                    'type': 'success' if result.get('ids') else 'warning',
                    'sticky': True,
                }
            }

        except UserError:
            raise
        except Exception as e:
            _logger.error("Erro na importação NFe: %s", str(e))
            raise UserError(_("Erro durante a importação: %s") % str(e))