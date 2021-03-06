# Copyright 2015-2016 Akretion
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, api, tools, fields, _
from odoo.exceptions import Warning as UserError
import os
from tempfile import mkstemp
import pkg_resources
import logging
logger = logging.getLogger(__name__)

try:
    from invoice2data.main import extract_data
    from invoice2data.extract.loader import read_templates
    from invoice2data.main import logger as loggeri2data
except ImportError:
    logger.debug('Cannot import invoice2data')


class AccountInvoiceImport(models.TransientModel):
    _inherit = 'account.invoice.import'

    @api.model
    def fallback_parse_pdf_invoice(self, file_data):
        '''This method must be inherited by additionnal modules with
        the same kind of logic as the account_bank_statement_import_*
        modules'''
        return self.invoice2data_parse_invoice(file_data)

    @api.model
    def invoice2data_parse_invoice(self, file_data):
        logger.info('Trying to analyze PDF invoice with invoice2data lib')
        fd, file_name = mkstemp()
        try:
            os.write(fd, file_data)
        except Exception as e:
            pass
        finally:
            os.close(fd)
        # Transfer log level of Odoo to invoice2data
        loggeri2data.setLevel(logger.getEffectiveLevel())
        local_templates_dir = tools.config.get(
            'invoice2data_templates_dir', False)
        logger.debug(
            'invoice2data local_templates_dir=%s', local_templates_dir)
        templates = []
        if local_templates_dir and os.path.isdir(local_templates_dir):
            templates += read_templates(local_templates_dir)
        exclude_built_in_templates = tools.config.get(
            'invoice2data_exclude_built_in_templates', False)
        if not exclude_built_in_templates:
            invoice2data_folder = pkg_resources.resource_filename(
                'invoice2data', 'extract/templates')
            templates += read_templates(invoice2data_folder)
        logger.debug(
            'Calling invoice2data.extract_data with templates=%s',
            templates)
        try:
            invoice2data_res = extract_data(file_name, templates=templates)
        except Exception as e:
            raise UserError(_(
                "PDF Invoice parsing failed. Error message: %s") % e)
        if not invoice2data_res:
            raise UserError(_(
                "This PDF invoice doesn't match a known template of "
                "the invoice2data lib."))
        logger.info(
            'Result of invoice2data PDF extraction: %s', invoice2data_res)
        return self.invoice2data_to_parsed_inv(invoice2data_res)

    @api.model
    def invoice2data_to_parsed_inv(self, invoice2data_res):
        date = fields.Date.to_string(invoice2data_res.get('date')) if invoice2data_res.get('date') else None
        date_due = fields.Date.to_string(invoice2data_res.get('date_due')) if invoice2data_res.get('date_due') else None
        date_start = fields.Date.to_string(invoice2data_res.get('date_start')) if invoice2data_res.get('date_start') else None
        date_end = fields.Date.to_string(invoice2data_res.get('date_end')) if invoice2data_res.get('date_end') else None

        parsed_inv = {
            'partner': {
                'vat': invoice2data_res.get('vat'),
                'name': invoice2data_res.get('partner_name'),
                'email': invoice2data_res.get('partner_email'),
                'website': invoice2data_res.get('partner_website'),
                'siren': invoice2data_res.get('siren'),
                },
            'currency': {
                'iso': invoice2data_res.get('currency'),
                },
            'amount_total': invoice2data_res.get('amount'),
            'invoice_number': invoice2data_res.get('invoice_number'),
            'date': date,
            'date_due': date_due,
            'date_start': date_start,
            'date_end': date_end,
            'description': invoice2data_res.get('description'),
            }
        if 'amount_untaxed' in invoice2data_res:
            parsed_inv['amount_untaxed'] = invoice2data_res['amount_untaxed']
        if 'amount_tax' in invoice2data_res:
            parsed_inv['amount_tax'] = invoice2data_res['amount_tax']
        return parsed_inv
