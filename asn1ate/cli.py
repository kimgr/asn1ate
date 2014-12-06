# Copyright (c) 2013, Schneider Electric Buildings AB
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of Schneider Electric Buildings AB nor the
#       names of contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import print_function  # Python 2 compatibility

import sys
from asn1ate import parser, sema, pyasn1gen
from asn1ate.support import pygen
import click


@click.command()
@click.option(
    '--stage',
    type=click.Choice(['parse', 'sema', 'gen']),
    default='gen',
    help='After which stage to stop, defaults to gen')
@click.option(
    '--output',
    type=click.File('rw'),
    default=sys.stdout,
    help='Output file name, stdout if not specified')
@click.argument(
    'asn1def',
    type=click.File('r'))
def main(stage, output, asn1def):
    '''
        Program that parses asn1def input file and parses it.

        Input ASN1DEF is the file (or stdin -) containing the ASN#1 definition.
    '''
    parse_tree = parser.parse_asn1(asn1def.read())
    if stage == 'parse':
        parser.print_parse_tree(parse_tree)
        return 0

    modules = sema.build_semantic_model(parse_tree)
    if stage == 'sema':
        for module in modules:
            print(module)
        return 0

    for module in modules:
        print(pygen.auto_generated_header(str(asn1def)))
        pyasn1gen.generate_pyasn1(module, output)
    return 0
