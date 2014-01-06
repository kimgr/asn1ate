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
from asn1ate import parser
from asn1ate.support import pygen
from asn1ate.sema import *


class Pyasn1Backend(object):
    """ Backend to generate pyasn1 declarations from semantic tree.
    Generators are divided into declarations and expressions,
    because types in pyasn1 can be declared either as class
    definitions or inline, e.g.

    # Foo ::= INTEGER
    # Foo is a decl
    class Foo(univ.Integer):
        pass

    # Seq ::= SEQUENCE {
    #     foo INTEGER
    # }
    # Seq is a decl,
    # univ.Integer is an expr
    class Seq(univ.Sequence):
        componentType = namedtype.NamedTypes(
            namedtype.NamedType('foo', univ.Integer())
        )

    Typically, declarations can contain other declarations
    or expressions, expressions can only contain other expressions.
    """
    def __init__(self, sema_module, out_stream):
        self.sema_module = sema_module
        self.writer = pygen.PythonWriter(out_stream)

        self.decl_generators = {
            ChoiceType: self.decl_constructed_type,
            SequenceType: self.decl_constructed_type,
            SetType: self.decl_constructed_type,
            TaggedType: self.decl_tagged_type,
            SimpleType: self.decl_simple_type,
            UserDefinedType: self.decl_userdefined_type,
            ValueListType: self.decl_value_list_type,
            BitStringType: self.decl_bitstring_type,
            SequenceOfType: self.decl_sequenceof_type,
            SetOfType: self.decl_setof_type,
            TypeAssignment: self.decl_type_assignment,
            ValueAssignment: self.decl_value_assignment
        }

        self.expr_generators = {
            TaggedType: self.expr_tagged_type,
            SimpleType: self.expr_simple_type,
            UserDefinedType: self.expr_userdefined_type,
            ComponentType: self.expr_component_type,
            NamedType: self.expr_named_type,
            SequenceOfType: self.expr_sequenceof_type,
            SetOfType: self.expr_setof_type,
            ValueListType: self.expr_value_list_type,
            ChoiceType: self.expr_constructed_type,
            SequenceType: self.expr_constructed_type,
            SetType: self.expr_constructed_type,
        }

    def generate_code(self):
        self.writer.write_line('from pyasn1.type import univ, char, namedtype, namedval, tag, constraint, useful')
        self.writer.write_blanks(2)

        # TODO: Only generate _OID if sema_module
        # contains object identifier values.
        self.generate_OID()
        self.writer.write_blanks(2)

        assignments = topological_sort(self.sema_module.assignments)
        for assignment in assignments:
            self.writer.write_block(self.generate_decl(assignment))
            self.writer.write_blanks(2)

    def generate_expr(self, t):
        generator = self.expr_generators[type(t)]
        return generator(t)

    def generate_decl(self, t):
        generator = self.decl_generators[type(t)]
        return generator(t)

    def decl_type_assignment(self, assignment):
        fragment = self.writer.get_fragment()

        assigned_type, type_decl = assignment.type_name, assignment.type_decl

        base_type = _translate_type(type_decl.type_name)
        fragment.write_line('class %s(%s):' % (assigned_type, base_type))

        fragment.push_indent()
        fragment.write_block(self.generate_decl(type_decl))
        fragment.pop_indent()

        return str(fragment)

    def expr_simple_type(self, t):
        type_expr = _translate_type(t.type_name) + '()'
        if t.constraint:
            type_expr += '.subtype(subtypeSpec=constraint.ValueRangeConstraint(%s, %s))' % (t.constraint.min_value, t.constraint.max_value)

        return type_expr

    def decl_simple_type(self, t):
        if t.constraint:
            return 'subtypeSpec = constraint.ValueRangeConstraint(%s, %s)' % (t.constraint.min_value, t.constraint.max_value)
        else:
            return 'pass'

    def expr_userdefined_type(self, t):
        return t.type_name + '()'

    def decl_userdefined_type(self, t):
        return 'pass'

    def decl_constructed_type(self, t):
        fragment = self.writer.get_fragment()

        fragment.write_line('componentType = namedtype.NamedTypes(')

        fragment.push_indent()
        fragment.write_block(self.expr_component_types(t.components))
        fragment.pop_indent()

        fragment.write_line(')')

        return str(fragment)

    def expr_constructed_type(self, t):
        fragment = self.writer.get_fragment()

        class_name = _translate_type(t.type_name)

        fragment.write_line('%s(componentType=namedtype.NamedTypes(' % class_name)

        fragment.push_indent()
        fragment.write_block(self.expr_component_types(t.components))
        fragment.pop_indent()

        fragment.write_line('))')

        return str(fragment)

    def expr_component_types(self, components):
        fragment = self.writer.get_fragment()

        component_exprs = []
        for c in components:
            if not isinstance(c, ExtensionMarker):
                component_exprs.append(self.generate_expr(c))

        fragment.write_enumeration(component_exprs)

        return str(fragment)

    def expr_tagged_type(self, t):
        tag_type = 'implicitTag' if t.implicit else 'explicitTag'
        type_expr = self.generate_expr(t.type_decl)
        type_expr += '.subtype(%s=%s)' % (tag_type, self.build_tag_expr(t))

        return type_expr

    def decl_tagged_type(self, t):
        fragment = self.writer.get_fragment()

        tag_type = 'tagImplicitly' if t.implicit else 'tagExplicitly'
        base_type = _translate_type(t.type_decl.type_name)
        fragment.write_line('tagSet = %s.tagSet.%s(%s)' % (base_type, tag_type, self.build_tag_expr(t)))
        fragment.write_line(self.generate_decl(t.type_decl))  # possibly 'pass'. but that's OK in a decl

        return str(fragment)

    def build_tag_expr(self, tag_def):
        context = _translate_tag_class(tag_def.class_name)

        tagged_type_decl = self.sema_module.resolve_type_decl(tag_def.type_decl)
        if isinstance(tagged_type_decl, ConstructedType):
            tag_format = 'tag.tagFormatConstructed'
        else:
            tag_format = 'tag.tagFormatSimple'

        return 'tag.Tag(%s, %s, %s)' % (context, tag_format, tag_def.class_number)

    def expr_component_type(self, t):
        if t.components_of_type:
            # COMPONENTS OF works like a literal include, so just
            # expand all components of the referenced type.
            included_type_decl = self.sema_module.resolve_type_decl(t.components_of_type)
            included_content = self.expr_component_types(included_type_decl.components)

            # Strip trailing newline from expr_component_types
            # to make the list line up
            return included_content.strip()

        if t.optional:
            return "namedtype.OptionalNamedType('%s', %s)" % (t.identifier, self.generate_expr(t.type_decl))
        elif t.default_value is not None:
            type_expr = self.generate_expr(t.type_decl)
            type_expr += '.subtype(value=%s)' % _translate_value(t.default_value)

            return "namedtype.DefaultedNamedType('%s', %s)" % (t.identifier, type_expr)
        else:
            return "namedtype.NamedType('%s', %s)" % (t.identifier, self.generate_expr(t.type_decl))

    def expr_named_type(self, t):
        return "namedtype.NamedType('%s', %s)" % (t.identifier, self.generate_expr(t.type_decl))

    def decl_value_list_type(self, t):
        fragment = self.writer.get_fragment()

        if t.named_values:
            fragment.write_line('namedValues = namedval.NamedValues(')
            fragment.push_indent()

            named_values = ['(\'%s\', %s)' % (v.identifier, v.value) for v in t.named_values if not isinstance(v, ExtensionMarker)]
            fragment.write_enumeration(named_values)

            fragment.pop_indent()
            fragment.write_line(')')
        else:
            fragment.write_line('pass')

        return str(fragment)

    def expr_value_list_type(self, t):
        class_name = _translate_type(t.type_name)
        if t.named_values:
            named_values = ['(\'%s\', %s)' % (v.identifier, v.value) for v in t.named_values if not isinstance(v, ExtensionMarker)]
            return '%s(namedValues=namedval.NamedValues(%s))' % (class_name, ', '.join(named_values))
        else:
            return class_name + '()'

    def decl_bitstring_type(self, t):
        fragment = self.writer.get_fragment()

        if t.named_bits:
            fragment.write_line('namedValues = namedval.NamedValues(')
            fragment.push_indent()

            named_bit_list = list(map(lambda v: '(\'%s\', %s)' % (v.identifier, v.value), t.named_bits))
            fragment.write_enumeration(named_bit_list)

            fragment.pop_indent()
            fragment.write_line(')')
        else:
            fragment.write_line('pass')

        return str(fragment)

    def expr_sequenceof_type(self, t):
        return 'univ.SequenceOf(componentType=%s)' % self.generate_expr(t.type_decl)

    def decl_sequenceof_type(self, t):
        return 'componentType = %s' % self.generate_expr(t.type_decl)

    def expr_setof_type(self, t):
        return 'univ.SetOf(componentType=%s)' % self.generate_expr(t.type_decl)

    def decl_setof_type(self, t):
        return 'componentType = %s' % self.generate_expr(t.type_decl)

    def decl_value_assignment(self, assignment):
        assigned_value, type_decl, value = assignment.value_name, assignment.type_decl, assignment.value

        if isinstance(value, ObjectIdentifierValue):
            value_constructor = self.build_object_identifier_value(value)
        elif isinstance(value, BinaryStringValue):
            value_type = _translate_type(type_decl.type_name)
            value_constructor = '%s(binValue=\'%s\')' % (value_type, value.value)
        elif isinstance(value, HexStringValue):
            value_type = _translate_type(type_decl.type_name)
            value_constructor = '%s(hexValue=\'%s\')' % (value_type, value.value)
        else:
            value_type = _translate_type(type_decl.type_name)
            value_constructor = '%s(%s)' % (value_type, value)

        return '%s = %s' % (assigned_value, value_constructor)

    def build_object_identifier_value(self, t):
        objid_components = []

        for c in t.components:
            if isinstance(c, NameForm):
                if c.name in REGISTERED_OID_NAMES:
                    objid_components.append(str(REGISTERED_OID_NAMES[c.name]))
                else:
                    objid_components.append(c.name)
            elif isinstance(c, NumberForm):
                objid_components.append(str(c.value))
            elif isinstance(c, NameAndNumberForm):
                objid_components.append(str(c.number.value))
            else:
                assert False

        return '_OID(%s)' % ', '.join(objid_components)

    def generate_OID(self):
        self.writer.write_line('def _OID(*components):')
        self.writer.push_indent()
        self.writer.write_line('output = []')
        self.writer.write_line('for x in tuple(components):')
        self.writer.push_indent()
        self.writer.write_line('if isinstance(x, univ.ObjectIdentifier):')
        self.writer.push_indent()
        self.writer.write_line('output.extend(list(x))')
        self.writer.pop_indent()
        self.writer.write_line('else:')
        self.writer.push_indent()
        self.writer.write_line('output.append(int(x))')
        self.writer.pop_indent()
        self.writer.pop_indent()
        self.writer.write_blanks(1)
        self.writer.write_line('return univ.ObjectIdentifier(output)')
        self.writer.pop_indent()

        self.writer.pop_indent()


def generate_pyasn1(sema_module, out_stream):
    return Pyasn1Backend(sema_module, out_stream).generate_code()


# Translation tables from ASN.1 primitives to pyasn1 primitives
_ASN1_TAG_CONTEXTS = {
    'APPLICATION': 'tag.tagClassApplication',
    'PRIVATE': 'tag.tagClassPrivate',
    'UNIVERSAL': 'tag.tagClassUniversal'
}


_ASN1_BUILTIN_VALUES = {
    'FALSE': '0',
    'TRUE': '1'
}


_ASN1_BUILTIN_TYPES = {
    'INTEGER': 'univ.Integer',
    'BOOLEAN': 'univ.Boolean',
    'NULL': 'univ.Null',
    'ENUMERATED': 'univ.Enumerated',
    'REAL': 'univ.Real',
    'BIT STRING': 'univ.BitString',
    'OCTET STRING': 'univ.OctetString',
    'CHOICE': 'univ.Choice',
    'SEQUENCE': 'univ.Sequence',
    'SET': 'univ.Set',
    'SEQUENCE OF': 'univ.SequenceOf',
    'SET OF': 'univ.SetOf',
    'OBJECT IDENTIFIER': 'univ.ObjectIdentifier',
    'UTF8String': 'char.UTF8String',
    'GeneralString': 'char.GeneralString',
    'NumericString': 'char.NumericString',
    'PrintableString': 'char.PrintableString',
    'IA5String': 'char.IA5String',
    'GeneralizedTime': 'useful.GeneralizedTime',
    'UTCTime': 'useful.UTCTime',
    'ObjectDescriptor': 'useful.ObjectDescriptor',  # In pyasn1 r1.2
}


def _translate_type(type_name):
    """ Translate ASN.1 built-in types to pyasn1 equivalents.
    Non-builtins are not translated.
    """
    return _ASN1_BUILTIN_TYPES.get(type_name, type_name)


def _translate_tag_class(tag_class):
    """ Translate ASN.1 tag class names to pyasn1 equivalents.
    Defaults to tag.tagClassContext if tag_class is not
    recognized.
    """
    return _ASN1_TAG_CONTEXTS.get(tag_class, 'tag.tagClassContext')


def _translate_value(value):
    """ Translate ASN.1 built-in values to Python equivalents.
    Unrecognized values are not translated.
    """
    return _ASN1_BUILTIN_VALUES.get(value, value)


# Simplistic command-line driver
def main(args):
    with open(args[0]) as f:
        asn1def = f.read()

    parse_tree = parser.parse_asn1(asn1def)

    modules = build_semantic_model(parse_tree)
    if len(modules) > 1:
        print('WARNING: More than one module generated to the same stream.', file=sys.stderr)

    for module in modules:
        print(pygen.auto_generated_header())
        generate_pyasn1(module, sys.stdout)

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
