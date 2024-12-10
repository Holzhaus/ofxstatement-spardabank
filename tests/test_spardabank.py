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

import os
import unittest

from ofxstatement.ui import UI
from ofxstatement_spardabank.plugin import SpardaBankPlugin


class SpardaBankTest(unittest.TestCase):
    def test_spardabank(self) -> None:
        plugin = SpardaBankPlugin(UI(), {})
        plugin.settings["bic"] = "GENODED1SPE"
        here = os.path.dirname(__file__)
        csv_filename = os.path.join(here, "umsaetze-1234567-2024-02-13-12-00-00.csv")

        parser = plugin.get_parser(csv_filename)
        statement = parser.parse()

        assert statement is not None
