# -*- coding: utf-8 -*-
# Copyright (c) 2024 Jan Holthuis <jan.holthuis@rub.de>
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# SPDX-License-Identifier: MIT

from ofxstatement.statement import Statement

import csv
import dataclasses
import datetime
import decimal
import enum
import hashlib
import io
import logging
import re
import typing
import zoneinfo

import ofxstatement
import ofxstatement.parser
import ofxstatement.plugin
import ofxstatement.statement
import schwifty
import schwifty.exceptions

TIMEZONE = zoneinfo.ZoneInfo("Europe/Berlin")


class AccountType(enum.StrEnum):
    CHECKING = "CHECKING"
    SAVINGS = "SAVINGS"


class SepaField(enum.StrEnum):
    END_TO_END_REF = "EREF+"  # Ende-zu-Ende-Referenz
    CUSTOMER_REF = "KREF+"  # Kund:inreferenz
    MANDATE_REF = "MREF+"  # Mandatsreferenz
    CREDITOR_ID = "CRED+"  # Creditor Identifier
    ORIGINATOR_ID = "DEBT+"  # Originators Identification Code
    IBAN = "IBAN+"  # IBAN
    BIC = "BIC+"  # Originators Identification Code
    REF = "SVWZ+"  # SEPA-Verwendungszweck
    DIFFERENT_ORIGINATOR = "ABWA+"  # abweichende:r Auftraggeber:in
    DIFFERENT_RECIPIENT = "ABWE+"  # abweichende:r Empfänger:in


@dataclasses.dataclass
class Metadata:
    title: str
    customer_name: str
    customer_number: str
    start_date: datetime.datetime
    end_date: datetime.datetime
    account_number: str
    account_balance: str
    account_currency: str
    account_type: AccountType


class SpardaDialect(csv.Dialect):
    lineterminator = "\n"
    delimiter = ";"
    quotechar = '"'
    quoting = csv.QUOTE_ALL


def find_account_type(haystack: str) -> AccountType | None:
    for needle, account_type in [
        ("SpardaGiro", AccountType.CHECKING),
        ("SpardaYoung", AccountType.CHECKING),
        ("SpardaTagesgeld", AccountType.SAVINGS),
    ]:
        if needle in haystack:
            return account_type

    return None


def parse_file_header(file: io.TextIOBase) -> Metadata:
    reader = csv.reader(file, dialect=SpardaDialect)
    row = next(reader)
    assert len(row) == 1
    title = row[0]

    account_type = find_account_type(title) or AccountType.CHECKING

    row = next(reader)
    assert len(row) == 0

    row = next(reader)
    assert len(row) == 2
    assert row[0] == "Kontoinhaber:"
    customer_name = row[1]

    row = next(reader)
    assert len(row) == 2
    assert row[0] == "Kundennummer:"
    customer_number = row[1]

    row = next(reader)
    assert len(row) == 0

    reader = csv.DictReader(file, dialect=SpardaDialect)
    row = next(reader)
    start_date = datetime.datetime.strptime(row["Umsätze ab"], "%d.%m.%Y").replace(
        tzinfo=TIMEZONE
    )
    end_date = datetime.datetime.strptime(row["Enddatum"], "%d.%m.%Y").replace(
        tzinfo=TIMEZONE
    )
    account_number = row["Kontonummer"]
    account_balance = row["Saldo"]
    account_currency = row["Währung"]

    reader = csv.reader(file, dialect=SpardaDialect)
    row = next(reader)
    assert len(row) == 2
    assert row[0] == "Weitere gewählte Suchoptionen:"
    assert row[1] == "keine"

    row = next(reader)
    assert len(row) == 0

    row = next(reader)
    assert len(row) == 0

    return Metadata(
        title=title,
        customer_name=customer_name,
        customer_number=customer_number,
        start_date=start_date,
        end_date=end_date,
        account_number=account_number,
        account_balance=account_balance,
        account_currency=account_currency,
        account_type=account_type,
    )


class SpardaBankPlugin(ofxstatement.plugin.Plugin):
    """Plugin for parsing CSV files from the German Sparda-Bank eG."""

    def get_parser(self, filename: str) -> "SpardaBankParser":
        if bic_str := self.settings.get("bic"):
            bic = schwifty.BIC(bic_str)
        else:
            raise ValueError("Please configure your bank's `bic` in the settings.")
        return SpardaBankParser(filename, bic)


class SpardaBankParser(ofxstatement.parser.StatementParser[dict[str, str]]):
    def __init__(self, filename: str, bic: schwifty.BIC) -> None:
        super().__init__()
        self.filename = filename
        self.header = None
        self.date_format = "%d.%m.%Y"
        self.bic = bic

    def parse(self) -> Statement:
        """Main entry point for parsers

        super() implementation will call to split_records and parse_record to
        process the file.
        """
        with open(self.filename, "r", encoding="latin1") as f:
            metadata = parse_file_header(f)
            reader = csv.reader(f, dialect=SpardaDialect)
            fieldnames = next(reader)
            self.reader = csv.DictReader(
                f, dialect=SpardaDialect, fieldnames=fieldnames
            )
            statement = super().parse()
            if bank_code := self.bic.country_bank_code:
                iban = schwifty.IBAN.generate(
                    country_code="DE",
                    bank_code=bank_code,
                    account_code=metadata.account_number,
                )
                statement.account_id = iban
                statement.bank_id = self.bic
            statement.currency = metadata.account_currency
            statement.start_date = metadata.start_date
            statement.end_date = metadata.end_date
            statement.end_balance = self.parse_decimal(metadata.account_balance)
            statement.account_type = AccountType[metadata.account_type]

            return statement

    def split_records(self) -> typing.Iterator[dict[str, str]]:
        """Return iterable object consisting of a line per transaction"""
        yield from (
            row
            for row in self.reader
            if row["Buchungstag"] != "* noch nicht ausgeführte Umsätze"
        )

    def parse_record(
        self, line: dict[str, str]
    ) -> ofxstatement.statement.StatementLine:
        """Parse given transaction line and return StatementLine object"""
        logger = logging.getLogger(__name__)
        booking_date = self.parse_datetime(line["Buchungstag"])
        value_date = self.parse_datetime(line["Wertstellungstag"])
        reference = remove_superfluous_reference_whitespace(line["Verwendungszweck"])
        amount = self.parse_decimal(line["Umsatz"])
        currency = ofxstatement.statement.Currency(symbol=line["Währung"])

        statement_line = ofxstatement.statement.StatementLine(
            date=value_date,
            memo=reference,
            amount=amount,
        )
        statement_line.date_user = booking_date
        statement_line.currency = currency

        h = hashlib.new("sha1")
        h.update(f"{reference} {amount} {currency.symbol}".encode("utf8"))

        statement_line.id = "{}{}".format(
            value_date.strftime("%Y%m%d"),
            h.hexdigest(),
        )

        fields = dict(self.parse_reference_fields(reference))
        logger.debug("Parsed field from reference: %r", fields)
        for field in [SepaField.REF, "card_payment_reference"]:
            if value := fields.get(field):
                statement_line.memo = value

        if value := fields.get(SepaField.IBAN):
            value = value.replace(" ", "")
            try:
                iban = schwifty.IBAN(value)
            except schwifty.exceptions.SchwiftyException as err:
                logger.warning("Failed to parse IBAN from %r: %r", value, err)
            else:
                bic = None
                if bic_value := fields.get(SepaField.BIC):
                    bic_value = bic_value.replace(" ", "")
                    try:
                        bic = schwifty.BIC(bic_value)
                    except schwifty.exceptions.SchwiftyException as err:
                        logger.warning(
                            "Failed to parse BIC from %r: %r", bic_value, err
                        )

                if bic is None:
                    bic = iban.bic

                if iban and bic:
                    bank_account = ofxstatement.statement.BankAccount(
                        bank_id=bic, acct_id=iban
                    )
                    if bic.branch_code:
                        bank_account.branch_id = bic.branch_code
                    statement_line.bank_account_to = bank_account

        if value := fields.get(SepaField.END_TO_END_REF):
            statement_line.check_no = value

        if value := fields.get("card_payment_datetime"):
            try:
                card_payment_datetime = datetime.datetime.strptime(
                    value,
                    "%d.%m.%Y %H.%M.%S",
                )
            except ValueError as err:
                logger.warning("Failed to parse datetime from %r: %r", value, err)
            else:
                statement_line.date_user = card_payment_datetime

        if value := fields.get("type"):
            statement_line.trntype = self.find_transaction_type(value)
        if statement_line.trntype is None:
            statement_line.trntype = "CREDIT" if amount > 0.0 else "DEBIT"

        if value := fields.get("recipient"):
            statement_line.payee = value

        return statement_line

    def parse_datetime(self, value: str) -> datetime.datetime:
        return super().parse_datetime(value).replace(tzinfo=TIMEZONE)

    def parse_decimal(self, value: str) -> decimal.Decimal:
        return decimal.Decimal(value.replace(".", "").replace(",", "."))

    def find_transaction_type(self, haystack: str) -> str | None:
        for needle, transaction_type in [
            ("SEPA-ÜBERWEISUNG", "XFER"),
            ("SEPA-LOHN/GEHALT", "XFER"),
            ("SEPA-BASISLASTSCHRIFT", "DIRECTDEBIT"),
            ("GIROCARD", "POS"),
            ("nicht GIRO", "POS"),
        ]:
            if needle in haystack:
                return transaction_type

    def parse_reference_fields(
        self, reference: str
    ) -> typing.Iterator[tuple[str, str]]:
        field = "default"
        start = 0
        for match in re.finditer(r"\b([A-Z]{3,4}\+) ", reference):
            end, new_start = match.span()
            value = reference[start:end].strip()
            if field == "default":
                value, other_fields = parse_default_field(value)
                yield from other_fields
            yield (field, value)
            start = new_start
            field = match.group(1)

        value = reference[start:].strip()
        if field == "default":
            value, other_fields = parse_default_field(value)
            yield from other_fields
        yield (field, value)


def parse_default_field(value: str) -> tuple[str, list[tuple[str, str]]]:
    for suffix in [
        "SEPA-ÜBERWEISUNG",
        "SEPA-LOHN/GEHALT",
        "SEPA-BASISLASTSCHRIFT",
    ]:
        if value.endswith(suffix):
            return ("", [("recipient", value[: -len(suffix)]), ("type", suffix)])

    if match := re.search(
        r"(?P<card_payment_reference>.*)"
        r"(?P<card_payment_datetime>\d{2}\.\d{2}\.\d{4} \d{2}\.\d{2}\.\d{2}) "
        r"(?:OFFLIN|\d{6}) "
        r"(?P<card_payment_currency>[A-Z]{3})\s+"
        r"(?P<card_payment_amount>-?\d+,\d{2}) "
        r"EC\s+[A-Z]*\d+\s*\d*\s*"
        r"PAN (?P<pan>\d+) "
        r"(?P<recipient>.*?)\d{3} "
        r"(?P<card_expiration>\d{2}/\d{4}) "
        r"(?P<type>GIROCARD|nicht GIRO) "
        r"(?P<card_data_entry_method>[A-Z]{4})/"
        r"(?P<card_payment_auth_method>[A-Z]{4})/+\d*",
        value,
    ):
        return (value[: match.span()[0]], list(match.groupdict().items()))

    return (value, [])


def remove_superfluous_reference_whitespace(value: str) -> str:
    i = 53
    while i < len(value):
        if value[i] == " ":
            value = value[:i] + value[i + 1 :]
        i += 54
    return value
