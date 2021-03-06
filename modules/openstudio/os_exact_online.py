# -*- coding: utf-8 -*-

from gluon import *


class OSExactOnline:
    def get_api(self):
        """
        Return ExactAPI linked to config and token storage
        """
        import os
        from exactonline.api import ExactApi
        from exactonline.exceptions import ObjectDoesNotExist
        from exactonline.storage import IniStorage

        storage = self.get_storage()

        return ExactApi(storage=storage)


    def get_storage(self):
        """
        Get ini storage
        """
        import os
        from ConfigParser import NoOptionError
        from exactonline.storage import IniStorage

        class MyIniStorage(IniStorage):
            def get_response_url(self):
                # Configure your custom response URL.
                return self.get_base_url() + '/exact_online/oauth2_success/'

        request = current.request

        config_file = os.path.join(
            request.folder,
            'private',
            'eo_config.ini'
        )

        return MyIniStorage(config_file)


    def create_sales_entry(self, os_invoice):
        """
        :param os_customer: OsCustomer object
        :param os_invoice: OsInvoice Object
        :return:
        """
        from exactonline.resource import GET
        from os_customer import Customer
        from tools import OsTools

        db = current.db
        os_tools = OsTools()
        authorized = os_tools.get_sys_property('exact_online_authorized')

        if not authorized:
            self._log_error(
                'create',
                'sales_entry',
                os_invoice.invoice.id,
                "Exact online integration not authorized"
            )

            return

        items = os_invoice.get_invoice_items_rows()
        if not len(items):
            return # Don't do anything for invoices without items


        import pprint

        from ConfigParser import NoOptionError
        from exactonline.http import HTTPError

        storage = self.get_storage()
        api = self.get_api()
        cuID = os_invoice.get_linked_customer_id()
        os_customer = Customer(os_invoice.get_linked_customer_id())
        eoID = os_customer.row.exact_online_relation_id

        if not eoID:
            self._log_error(
                'create',
                'sales_entry',
                os_invoice.invoice.id,
                "This customer is not linked to Exact Online - " + unicode(os_customer.row.id)
            )
            return

        try:
            selected_division = int(storage.get('transient', 'division'))
        except NoOptionError:
            selected_division = None

        amounts = os_invoice.get_amounts()

        remote_journal = os_invoice.invoice_group.JournalID
        invoice_date = os_invoice.invoice.DateCreated
        is_credit_invoice = os_invoice.is_credit_invoice()
        local_invoice_number = os_invoice.invoice.id
        payment_method = os_invoice.get_payment_method()

        invoice_data = {
            'AmountDC': str(amounts.TotalPriceVAT),  # DC = default currency
            'AmountFC': str(amounts.TotalPriceVAT),  # FC = foreign currency
            'EntryDate': invoice_date.strftime('%Y-%m-%dT%H:%M:%SZ'),  # pretend we're in UTC
            'Customer': eoID,
            'Description': os_invoice.invoice.Description,
            'Journal': remote_journal,  # 70 "Verkoopboek"
            'ReportingPeriod': invoice_date.month,
            'ReportingYear': invoice_date.year,
            'SalesEntryLines': self.format_os_sales_entry_lines(os_invoice),
            'VATAmountDC': str(amounts.VAT),
            'VATAmountFC': str(amounts.VAT),
            'YourRef': local_invoice_number,
        }

        if payment_method and payment_method.AccountingCode:
            invoice_data['PaymentCondition'] = payment_method.AccountingCode

        if is_credit_invoice:
            invoice_data['Type'] = 21


        error = False

        try:
            result = api.invoices.create(invoice_data)
            #
            # print "Create invoice result:"
            # pp = pprint.PrettyPrinter(depth=6)
            # pp.pprint(result)

            eoseID = result['EntryID']
            os_invoice.invoice.ExactOnlineSalesEntryID = eoseID
            os_invoice.invoice.InvoiceID = result['EntryNumber']
            os_invoice.invoice.update_record()

            uri = result[u'SalesEntryLines'][u'__deferred']['uri']
            entry_lines = api.restv1(GET(str(uri)))
            # pp.pprint(entry_lines)

            for i, line in enumerate(entry_lines):
                query = (db.invoices_items.invoices_id == os_invoice.invoice.id) & \
                        (db.invoices_items.Sorting == i + 1)
                db(query).update(ExactOnlineSalesEntryLineID = line['ID'])

        except HTTPError as e:
            error = True
            self._log_error(
                'create',
                'sales_entry',
                os_invoice.invoice.id,
                e
            )

        if error:
            return False

        return eoseID


    def update_sales_entry(self, os_invoice):
        """
        :param os_customer: OsCustomer object
        :return: None
        """
        from exactonline.resource import GET

        from os_customer import Customer
        from tools import OsTools

        os_tools = OsTools()
        authorized = os_tools.get_sys_property('exact_online_authorized')

        if not authorized:
            self._log_error(
                'update',
                'sales_entry',
                os_invoice.invoice.id,
                "Exact online integration not authorized"
            )

            return

        items = os_invoice.get_invoice_items_rows()
        if not len(items):
            return True # Don't do anything for invoices without items, but mark as error

        eoseID = os_invoice.invoice.ExactOnlineSalesEntryID

        if not eoseID:
            eoseID = self.create_sales_entry(os_invoice)
            if not eoseID:
                return True # This returns an error
            return False # No error, created successfully


        import pprint

        from ConfigParser import NoOptionError
        from exactonline.http import HTTPError

        storage = self.get_storage()
        api = self.get_api()
        cuID = os_invoice.get_linked_customer_id()
        os_customer = Customer(os_invoice.get_linked_customer_id())

        try:
            selected_division = int(storage.get('transient', 'division'))
        except NoOptionError:
            selected_division = None

        amounts = os_invoice.get_amounts()

        remote_journal = os_invoice.invoice_group.JournalID
        invoice_date = os_invoice.invoice.DateCreated
        is_credit_invoice = os_invoice.is_credit_invoice()
        local_invoice_number = os_invoice.invoice.id
        payment_method = os_invoice.get_payment_method()

        invoice_data = {
            'AmountDC': str(amounts.TotalPriceVAT),  # DC = default currency
            'AmountFC': str(amounts.TotalPriceVAT),  # FC = foreign currency
            'EntryDate': invoice_date.strftime('%Y-%m-%dT%H:%M:%SZ'),  # pretend we're in UTC
            'Customer': os_customer.row.exact_online_relation_id,
            'Description': os_invoice.invoice.Description,
            'Journal': remote_journal,  # 70 "Verkoopboek"
            'ReportingPeriod': invoice_date.month,
            'ReportingYear': invoice_date.year,
            'VATAmountDC': str(amounts.VAT),
            'VATAmountFC': str(amounts.VAT),
            'YourRef': local_invoice_number,
        }

        if payment_method and payment_method.AccountingCode:
            invoice_data['PaymentCondition'] = payment_method.AccountingCode
            
        if is_credit_invoice:
            invoice_data['Type'] = 21

        error = False

        try:
            result = api.invoices.update(eoseID, invoice_data)
            # print "Update invoice result:"
            # pp = pprint.PrettyPrinter(depth=6)
            # pp.pprint(result)

            errors_update_lines = self.update_sales_entry_lines(os_invoice)

            if errors_update_lines:
                error = True

        except HTTPError as e:
            error = True
            self._log_error(
                'update',
                'sales_entry',
                os_invoice.invoice.id,
                e
            )

        return error


    def create_sales_entry_line(self, line):
        """
        :param line: dict
        :return:
        """
        api = self.get_api()
        error = False
        result = ''

        try:
            result = api.salesentrylines.create(line)
        except HTTPError as e:
            error = True
            self._log_error(
                'create',
                'sales_entry_line',
                None,
                e
            )

        return dict(error=error, result=result)


    def update_sales_entry_line(self, ID, line):
        """
        :param line: dict
        :return:
        """
        api = self.get_api()

        error = False
        result = ''

        try:
            result = api.salesentrylines.update(ID, line)
        except HTTPError as e:
            error = True
            self._log_error(
                'update',
                'sales_entry_line',
                ID,
                e
            )

        return dict(error=error, result=result)


    def delete_sales_entry_line(self, ID):
        """
        :param ID: Exact Online SalesEntryLine ID
        :return:
        """
        api = self.get_api()

        return api.salesentrylines.delete(ID)


    def update_sales_entry_lines(self, os_invoice):
        """
        :param os_invoice: Invoice object
        :return:
        """
        db = current.db

        is_credit_invoice = os_invoice.is_credit_invoice()

        count_errors = 0
        items = os_invoice.get_invoice_items_rows()

        for item in items:
            if not item.accounting_glaccounts_id:
                self._log_error(
                    'format',
                    'invoice_item',
                    item.id,
                    "G/L Account Code not set"
                )
                continue # Break loop and go to next item. GLAccount is a mandatory field

            os_glaccount = db.accounting_glaccounts(
                item.accounting_glaccounts_id
            )

            glaccount = self.get_glaccount(os_glaccount.AccountingCode)

            if not item.tax_rates_id:
                self._log_error(
                    'format',
                    'invoice_item',
                    item.id,
                    "Tax rate not set"
                )
                continue # Break loop and go to next item. Tax rate is a mandatory field

            tax_rate = db.tax_rates(item.tax_rates_id)

            line = {
                'AmountFC': item.TotalPrice,
                'Description': '%s %s' %(item.ProductName, item.Description),
                'GLAccount': glaccount[0][u'ID'],
                'Quantity': item.Quantity,
                'VATCode': tax_rate.VATCodeID
            }

            if is_credit_invoice:
                line['Type'] = 21

            if item.accounting_costcenters_id:
                ac = db.accounting_costcenters(
                    item.accounting_costcenters_id
                )
                line['CostCenter'] = ac.AccountingCode

            ID = item.ExactOnlineSalesEntryLineID

            if not ID: # Create
                line['AmountDC'] = item.TotalPrice
                line['EntryID'] = os_invoice.invoice.ExactOnlineSalesEntryID

                result = self.create_sales_entry_line(line)
                if result['error']:
                    count_errors += 1

                item.ExactOnlineSalesEntryLineID = result['ID']
                item.update_record()

            else: # Update
                result = self.update_sales_entry_line(ID, line)

                if result['error']:
                    count_errors += 1

        return count_errors


    def get_glaccount(self, code):
        """
        :param code: Exact G/L Account code. eg. 0150
        :return: glaccount dict
        """
        api = self.get_api()

        return api.financialglaccounts.filter(Code=code)


    def get_journal(self, code):
        """
        :param code: Exact G/L Account code. eg. 0150
        :return: glaccount dict
        """
        api = self.get_api()

        return api.financialjournals.filter(Code=code)


    def get_sales_entry(self, os_invoice):
        """
        :param os_invoice: Invoice object
        :return: SalesEntry dict
        """
        api = self.get_api()

        return api.invoices.filter(
            invoice_number=unicode(os_invoice.invoice.id)
        )


    def format_os_sales_entry_lines(self, os_invoice):
        """
        GLAccount is gotten from API for each call
        :param os_invoice: Invoice object
        :return: SalesEntryLines dict
        """
        db = current.db

        is_credit_invoice = os_invoice.is_credit_invoice()
        items = os_invoice.get_invoice_items_rows()

        lines = []
        for item in items:
            if not item.accounting_glaccounts_id:
                self._log_error(
                    'format',
                    'invoice_item',
                    item.id,
                    "G/L Account Code not set"
                )
                continue # Break loop and go to next item. GLAccount is a mandatory field

            os_glaccount = db.accounting_glaccounts(
                item.accounting_glaccounts_id
            )

            glaccount = self.get_glaccount(os_glaccount.AccountingCode)

            if not item.tax_rates_id:
                self._log_error(
                    'format',
                    'invoice_item',
                    item.id,
                    "Tax rate not set"
                )
                continue # Break loop and go to next item. Tax rate is a mandatory field

            tax_rate = db.tax_rates(item.tax_rates_id)

            line = {
                'AmountDC': item.TotalPrice,
                'AmountFC': item.TotalPrice,
                'Description': '%s %s' %(item.ProductName, item.Description),
                'GLAccount': glaccount[0][u'ID'],
                'Quantity': item.Quantity,
                'VATCode': tax_rate.VATCodeID,
            }

            if is_credit_invoice:
                line['Type'] = 21

            if item.accounting_costcenters_id:
                ac = db.accounting_costcenters(
                    item.accounting_costcenters_id
                )
                line['CostCenter'] = ac.AccountingCode

            lines.append(line)


        return lines


    def create_relation(self, os_customer):
        """
        :param os_customer: OsCustomer object
        :return: exact online relation id
        """
        from tools import OsTools

        os_tools = OsTools()
        authorized = os_tools.get_sys_property('exact_online_authorized')

        if not authorized:
            self._log_error(
                'create',
                'relation',
                os_customer.row.id,
                "Exact online integration not authorized"
            )

            return

        else:
            import pprint

            from ConfigParser import NoOptionError
            from exactonline.http import HTTPError

            storage = self.get_storage()
            api = self.get_api()

            try:
                selected_division = int(storage.get('transient', 'division'))
            except NoOptionError:
                selected_division = None


            relation_dict = {
                "AddressLine1": os_customer.row.address,
                "ChamberOfCommerce": os_customer.row.company_registration,
                "City": os_customer.row.city,
                "Code": os_customer.row.id,
                "Country": os_customer.row.country,
                "Division": selected_division,
                "Email": os_customer.row.email,
                "Name": os_customer.row.display_name,
                "Phone": os_customer.row.phone,
                "Postcode": os_customer.row.postcode,
                "Status": "C", # Customer
                "VATNumber": os_customer.row.company_tax_registration,
                "Website": os_customer.row.teacher_website
            }

            error = False

            try:
                result = api.relations.create(relation_dict)
                rel_id = result['ID']

                os_customer.row.exact_online_relation_id = rel_id
                os_customer.row.update_record()

            except HTTPError as e:
                error = True
                self._log_error(
                    'create',
                    'relation',
                    os_customer.row.id,
                    e
                )

            if error:
                return False

            return rel_id


    def update_relation(self, os_customer):
        """
        :param os_customer: OsCustomer object
        :return: dict(error=True|False, message='')
        """
        from tools import OsTools

        os_tools = OsTools()
        authorized = os_tools.get_sys_property('exact_online_authorized')

        if not authorized:
            self._log_error(
                'create',
                'relation',
                os_customer.row.id,
                "Exact online integration not authorized"
            )

            return

        eoID = os_customer.row.exact_online_relation_id

        if not eoID:
            self.create_relation(os_customer)
            return

        import pprint

        from ConfigParser import NoOptionError
        from exactonline.http import HTTPError

        storage = self.get_storage()
        api = self.get_api()

        try:
            selected_division = int(storage.get('transient', 'division'))
        except NoOptionError:
            selected_division = None

        relation_dict = {
            "AddressLine1": os_customer.row.address,
            "Name": os_customer.row.display_name,
            "ChamberOfCommerce": os_customer.row.company_registration,
            "City": os_customer.row.city,
            "Code": os_customer.row.id,
            "Country": os_customer.row.country,
            "Email": os_customer.row.email,
            "Phone": os_customer.row.phone,
            "Postcode": os_customer.row.postcode,
            "Status": "C", # Customer
            "VATNumber": os_customer.row.company_tax_registration,
            "Website": os_customer.row.teacher_website
        }

        error = False
        message = ''

        try:
            result = api.relations.update(eoID, relation_dict)
        except HTTPError as e:
            error = True
            message = e

            self._log_error(
                'update',
                'relation',
                os_customer.row.id,
                e
            )


        return dict(error=error, message=message)


    def get_bankaccount(self, os_customer):
        """
        :param os_customer: OsCustomer object
        :return: ExactOnline bankaccount for os_customer
        """
        eoID = os_customer.row.exact_online_relation_id

        import pprint

        from ConfigParser import NoOptionError
        from exactonline.http import HTTPError

        storage = self.get_storage()
        api = self.get_api()

        try:
            return api.bankaccounts.filter(account=eoID)
        except HTTPError as e:
            error = True
            self._log_error(
                'get',
                'bankaccount',
                os_customer.row.id,
                e
            )
            return False


    def create_bankaccount(self, os_customer, os_customer_payment_info):
        """
        :param os_customer: OsCustomer object
        :return: None
        """
        from exactonline.http import HTTPError
        from tools import OsTools

        os_tools = OsTools()
        authorized = os_tools.get_sys_property('exact_online_authorized')

        if not authorized:
            self._log_error(
                'create',
                'bankaccount',
                os_customer.row.id,
                "Exact online integration not authorized"
            )

            return

        api = self.get_api()
        eoID = os_customer.row.exact_online_relation_id

        bank_account_dict = {
            'Account': eoID,
            'BankAccount': os_customer_payment_info.row.AccountNumber,
            'BankAccountHolderName': os_customer_payment_info.row.AccountHolder,
            'BICCode': os_customer_payment_info.row.BIC
        }

        eo_bankaccount_id = None

        # print "bank account creation result:"
        # result = api.bankaccounts.create(bank_account_dict)
        #
        # import pprint
        # pp = pprint.PrettyPrinter(depth=6)
        # pp.pprint(result)
        #
        # eo_bankaccount_id = result['ID']
        # os_customer_payment_info.row.exact_online_bankaccount_id = eo_bankaccount_id
        # os_customer_payment_info.row.update_record()

        try:
            result = api.bankaccounts.create(bank_account_dict)

            # print "bank account creation result:"
            # import pprint
            # pp = pprint.PrettyPrinter(depth=6)
            # pp.pprint(result)

            eo_bankaccount_id = result['ID']
            os_customer_payment_info.row.exact_online_bankaccount_id = eo_bankaccount_id
            os_customer_payment_info.row.update_record()

        except HTTPError as e:
            error = True
            self._log_error(
                'create',
                'bankaccount',
                os_customer_payment_info.row.id,
                e
            )

        return eo_bankaccount_id


    def update_bankaccount(self, os_customer, os_customer_payment_info):
        """
        :param os_customer: OsCustomer object
        :return: None
        """
        from exactonline.http import HTTPError
        from tools import OsTools

        os_tools = OsTools()
        authorized = os_tools.get_sys_property('exact_online_authorized')

        if not authorized:
            self._log_error(
                'update',
                'bankaccount',
                os_customer.row.id,
                "Exact online integration not authorized"
            )

            return

        api = self.get_api()
        eoID = os_customer.row.exact_online_relation_id

        exact_account = self.get_bankaccount(os_customer)
        if not len(exact_account):
            self.create_bankaccount(os_customer, os_customer_payment_info)

        bank_account_dict = {
            'Account': eoID,
            'BankAccount': os_customer_payment_info.row.AccountNumber,
            'BankAccountHolderName': os_customer_payment_info.row.AccountHolder,
            'BICCode': os_customer_payment_info.row.BIC
        }

        try:
            # print 'actually updating account'
            # print os_customer_payment_info.row.exact_online_bankaccount_id
            api.bankaccounts.update(
                os_customer_payment_info.row.exact_online_bankaccount_id,
                bank_account_dict
            )
        except HTTPError as e:
            error = True
            self._log_error(
                'update',
                'bankaccount',
                os_customer.row.id,
                e
            )


    def create_dd_mandate(self, os_customer_payment_info, os_cpim):
        """
        :param os_customer_payment_info: payment info object
        :param os_cpim: payment info mandates object
        :return:
        """
        from exactonline.http import HTTPError
        from tools import OsTools
        from os_customer import Customer

        TODAY_LOCAL = current.TODAY_LOCAL
        os_tools = OsTools()
        authorized = os_tools.get_sys_property('exact_online_authorized')


        if not authorized:
            self._log_error(
                'create',
                'directdebitmandate',
                os_cpim.cpimID,
                "Exact online integration not authorized"
            )

            return

        api = self.get_api()

        customer = Customer(os_customer_payment_info.row.auth_customer_id)
        eoID = customer.row.exact_online_relation_id
        if not eoID:
            eoID = self.create_relation(customer)

        eo_bankaccount_id = os_customer_payment_info.row.exact_online_bankaccount_id

        # print os_customer_payment_info.row

        if not eo_bankaccount_id:
            eo_bankaccount_id = self.create_bankaccount(customer, os_customer_payment_info)


        mandate_dict = {
            'Account': eoID,
            'BankAccount': eo_bankaccount_id,
            'Reference': os_cpim.row.MandateReference,
            'SignatureDate': TODAY_LOCAL.strftime("%Y-%m-%d")
        }


        try:
            result = api.directdebitmandates.create(mandate_dict)
            os_cpim.row.exact_online_directdebitmandates_id = result['ID']
            os_cpim.row.update_record()

        except HTTPError as e:
            error = True
            self._log_error(
                'create',
                'mandate',
                os_customer_payment_info.cpiID,
                e
            )


    def update_dd_mandate(self):
        """

        :return:
        """
        pass


    def delete_dd_mandate(self, mandateID):
        """

        :return:
        """
        T = current.T
        session = current.globalenv['session']
        from exactonline.http import HTTPError

        api = self.get_api()
        try:
            api.directdebitmandates.delete(mandateID)
        except HTTPError as e:
            self._log_error(
                'delete',
                'direct debit mandate',
                mandateID,
                e
            )

            session.flash = T("Failed to delete this mandate in Exact Online, it's probably in use somewhere.")


    def _log_error(self, action, object, object_id, result):
        """
        :param action: should be in ['create', 'read', 'update', 'delete']
        :param object: object name
        :param object_id: object id
        :param message: string
        :return: None
        """
        db = current.db

        db.integration_exact_online_log.insert(
            ActionName = action,
            ObjectName = object,
            ObjectID = object_id,
            ActionResult = result,
            Status = 'fail'
        )



# class ExactOnlineStorage(ExactOnlineConfig):
#     def get_response_url(self):
#         """Configure your custom response URL."""
#         return self.get_base_url() + '/exact_online/oauth2_success/'
#
#     def get(self, section, option):
#         option = self._get_value(section, option)
#
#         if not option:
#             raise ValueError('Required option is not set')
#
#         return option
#
#     def set(self, section, option, value):
#         self._set_value(section, option, value)
#
#
#     def _get_value(self, section, option):
#         """
#
#         :param section:
#         :param option:
#         :return:
#         """
#         db = current.db
#
#         query = (db.integration_exact_online_storage.ConfigSection == section) & \
#                 (db.integration_exact_online_storage.ConfigOption == option)
#         rows = db(query).select(db.integration_exact_online_storage.ConfigValue)
#
#         value = None
#         if rows:
#             value = rows.first().ConfigValue
#
#         return value
#
#
#     def _set_value(self, section, option, value):
#         """
#
#         :param section:
#         :param option:
#         :return:
#         """
#         db = current.db
#
#         query = (db.integration_exact_online_storage.ConfigSection == section) & \
#                 (db.integration_exact_online_storage.ConfigOption == option)
#         rows = db(query).select(db.integration_exact_online_storage.ALL)
#
#         if rows:
#             row = rows.first()
#             row.ConfigValue = value
#             row.update_record()
#         else:
#             db.integration_exact_online_storage.insert(
#                 ConfigSection = section,
#                 ConfigOption = option,
#                 ConfigValue = value
#             )
#
