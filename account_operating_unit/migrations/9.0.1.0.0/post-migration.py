# -*- coding: utf-8 -*-
# Copyright 2017 Eficent - Miquel Raich
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from openupgradelib import openupgrade


def map_account_journal_operating_unit_id(cr):
    cr.execute(
        """
        UPDATE account_journal aj
        SET operating_unit_id = aa.%s
        FROM account_account aa
        WHERE aj.default_credit_account_id = aa.id OR 
              aj.default_debit_account_id = aa.id
        """ % openupgrade.get_legacy_name('operating_unit_id')
    )


@openupgrade.migrate(use_env=False)
def migrate(cr, version):
    map_account_journal_operating_unit_id(cr)
