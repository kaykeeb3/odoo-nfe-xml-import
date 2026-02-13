# -*- coding: utf-8 -*-
{
    'name': "Importação de XML NFe para Estoque e Inventário",
    'version': '18.0.1.0.0',
    'summary': 'Importação de XML de NFe com atualização automática de estoque e inventário',
    'description': """
Importação de XML NFe para Estoque
==================================
Este módulo otimiza a entrada de mercadorias no Odoo através da leitura de arquivos XML de Nota Fiscal Eletrônica.

**Principais Funcionalidades:**
* Importação automatizada de arquivos XML de NFe para o Inventário.
* Atualização em tempo real dos níveis de estoque após processamento.
* Criação automática de produtos e parceiros caso não existam.
* Registro histórico de NFes processadas para evitar duplicidade.
* Totalmente integrado aos módulos de Estoque (Stock) e Compras.
    """,
    'author': 'PineappleTech',
    'website': 'https://pineappletec.com.br',
    'category': 'Inventory/Inventory',
    'depends': ['base', 'stock', 'product', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/nfe_import_views.xml',
        'views/nfe_wizard_views.xml',
    ],
    'images': [
        'static/description/main_screenshot.png',
    ],
    'license': 'OPL-1',
    'price': 150.00,
    'currency': 'BRL',
    'installable': True,
    'application': True,
    'auto_install': False,
    'external_dependencies': {
        'python': ['lxml'],
    },
}