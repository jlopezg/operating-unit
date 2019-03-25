# -*- coding: utf-8 -*-
# Copyright 2016-17 Eficent Business and IT Consulting Services S.L.
# Copyright 2016-17 Serpent Consulting Services Pvt. Ltd.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import _, api, fields, models
from odoo.tools import float_compare
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class HrPayslip(models.Model):

    _inherit = 'hr.payslip'

    operating_unit_id = fields.Many2one(
        related='contract_id.operating_unit_id')

    @api.multi
    def write(self, vals):
        res = super(HrPayslip, self).write(vals)
        if vals.get('move_id', False):
            for slip in self:
                if slip.operating_unit_id:
                    slip.move_id.operating_unit_id = slip.operating_unit_id.id
                    if slip.move_id.line_ids:
                        slip.move_id.line_ids.\
                            write({'operating_unit_id':
                                   slip.operating_unit_id.id})
        return res

    @api.model
    def prepare_debit_line(self, line, debit_account_id, slip, date, amount):
        return {
            'name': line.name,
            'partner_id': line._get_partner_id(credit_account=False),
            'account_id': debit_account_id,
            'journal_id': slip.journal_id.id,
            'date': date,
            'debit': amount > 0.0 and amount or 0.0,
            'credit': amount < 0.0 and -amount or 0.0,
            'analytic_account_id': line.salary_rule_id.analytic_account_id.id,
            'tax_line_id': line.salary_rule_id.account_tax_id.id,
            'operating_unit_id': slip.operating_unit_id.id}

    @api.model
    def prepare_credit_line(self, line, credit_account_id, slip, date, amount):
        return {
            'name': line.name,
            'partner_id': line._get_partner_id(credit_account=True),
            'account_id': credit_account_id,
            'journal_id': slip.journal_id.id,
            'date': date,
            'debit': amount < 0.0 and -amount or 0.0,
            'credit': amount > 0.0 and amount or 0.0,
            'analytic_account_id': line.salary_rule_id.analytic_account_id.id,
            'tax_line_id': line.salary_rule_id.account_tax_id.id,
            'operating_unit_id': slip.operating_unit_id.id
        }

    @api.model
    def prepare_adj_entry_credit(
            self, acc_id, slip, date, debit_sum, credit_sum):
        return {
            'name': _('Adjustment Entry'),
            'partner_id': False,
            'account_id': acc_id,
            'journal_id': slip.journal_id.id,
            'date': date,
            'debit': 0.0,
            'credit': debit_sum - credit_sum,
            'operating_unit_id': slip.operating_unit_id.id}

    @api.model
    def prepare_adj_entry_debit(
            self, acc_id, slip, date, debit_sum, credit_sum):
        return {
            'name': _('Adjustment Entry'),
            'partner_id': False,
            'account_id': acc_id,
            'journal_id': slip.journal_id.id,
            'date': date,
            'debit': credit_sum - debit_sum,
            'credit': 0.0,
            'operating_unit_id': slip.operating_unit_id.id}

    @api.multi
    def action_payslip_done(self):
        """Hook to allow changes in move lines"""
        self.compute_sheet()
        res = self.write({'state': 'done'})
        precision = self.env['decimal.precision'].precision_get('Payroll')
        for slip in self:
            line_ids = []
            debit_sum = 0.0
            credit_sum = 0.0
            date = slip.date or slip.date_to

            name = _('Payslip of %s') % (slip.employee_id.name)
            move_dict = {
                'narration': name,
                'ref': slip.number,
                'journal_id': slip.journal_id.id,
                'date': date,
            }
            for line in slip.details_by_salary_rule_category:
                amount = slip.credit_note and -line.total or line.total
                if float_is_zero(amount, precision_digits=precision):
                    continue
                debit_account_id = line.salary_rule_id.account_debit.id
                credit_account_id = line.salary_rule_id.account_credit.id

                if debit_account_id:
                    db_dict = self.prepare_debit_line(
                        line, debit_account_id, slip, date, amount)
                    debit_line = (0, 0, db_dict)
                    line_ids.append(debit_line)
                    debit_sum += debit_line[2]['debit'] - debit_line[2]['credit']

                if credit_account_id:
                    dr_dicc = self.prepare_credit_line(
                        line, credit_account_id, slip, date, amount)
                    credit_line = (0, 0, dr_dicc)
                    line_ids.append(credit_line)
                    credit_sum += credit_line[2]['credit'] - credit_line[2]['debit']

            if float_compare(credit_sum, debit_sum, precision_digits=precision) == -1:
                acc_id = slip.journal_id.default_credit_account_id.id
                if not acc_id:
                    raise UserError(_('The Expense Journal "%s" has not properly configured the Credit Account!') % (slip.journal_id.name))
                adj_credit = self.prepare_adj_entry_credit(
                    acc_id, slip, date, debit_sum, credit_sum)
                adjust_credit = (0, 0, adj_credit)
                line_ids.append(adjust_credit)

            elif float_compare(debit_sum, credit_sum, precision_digits=precision) == -1:
                acc_id = slip.journal_id.default_debit_account_id.id
                if not acc_id:
                    raise UserError(_('The Expense Journal "%s" has not properly configured the Debit Account!') % (slip.journal_id.name))
                adj_debit = self.prepare_adj_entry_debit(
                    acc_id, slip, date, debit_sum, credit_sum)
                adjust_debit = (0, 0, adj_debit)
                line_ids.append(adjust_debit)
            move_dict['line_ids'] = line_ids
            move = self.env['account.move'].create(move_dict)
            slip.write({'move_id': move.id, 'date': date})
            move.post()
        return res
