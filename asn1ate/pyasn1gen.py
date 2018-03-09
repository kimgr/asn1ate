# Copyright (c) 2013-2018, Schneider Electric Buildings AB
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
import argparse
import keyword
from asn1ate import parser, __version__
from asn1ate.support import pygen
from asn1ate.sema import *


class Pyasn1Backend(object):
    """ Backend to generate pyasn1 declarations from semantic tree.

    Pyasn1 represents type assignments as class derivation, e.g.

        # Foo ::= INTEGER
        class Foo(univ.Integer):
            pass

    For constructed types, the component types are instantiated inline, e.g.

        # Seq ::= SEQUENCE {
        #     foo INTEGER
        # }
        class Seq(univ.Sequence):
             componentType = namedtype.NamedTypes(
                namedtype.NamedType('foo', univ.Integer())
             )

    (univ.Integer is not a base class here, but a value.)

    To cope with circular dependencies, we define types in two passes so we'll
    generate the above as:

        class Seq(univ.Sequence):
            pass

        Seq.componentType = namedtype.NamedTypes(
            namedtype.NamedType('foo', univ.Integer())
        )

    This is nice, because we separate the introduction of a name (``Seq``) from
    the details of what it contains, so we can build recursive definitions
    without getting into trouble with Python's name lookup.

    We call the empty class a *declaration*, and the population of its members
    *definition*. The instantiation of univ.Integer is called an
    *inline definition*.

    The translation from ASN.1 constructs to Pyasn1 come in different flavors,
    depending on whether they're declarations, definitions or inline
    definitions.

    Only type and value assignments generate declarations. For type assignments
    we generate a definition once all dependent declarations are created. If the
    type assignment involves a constructed type, it is filled with inline
    definitions.
    """

    def __init__(self, sema_module, out_stream, referenced_modules):
        self.sema_module = sema_module
        self.referenced_modules = referenced_modules
        self.writer = pygen.PythonWriter(out_stream)

        self.decl_generators = {
            TypeAssignment: self.decl_type_assignment,
            ValueAssignment: self.decl_value_assignment
        }

        self.defn_generators = {
            ChoiceType: self.defn_constructed_type,
            SequenceType: self.defn_constructed_type,
            SetType: self.defn_constructed_type,
            SequenceOfType: self.defn_collection_type,
            SetOfType: self.defn_collection_type,
            TaggedType: self.defn_tagged_type,
            SelectionType: self.defn_selection_type,
            SimpleType: self.defn_simple_type,
            DefinedType: self.defn_defined_type,
            ValueListType: self.defn_value_list_type,
            BitStringType: self.defn_bitstring_type,
        }

        self.inline_generators = {
            TaggedType: self.inline_tagged_type,
            SelectionType: self.inline_selection_type,
            SimpleType: self.inline_simple_type,
            DefinedType: self.inline_defined_type,
            ComponentType: self.inline_component_type,
            NamedType: self.inline_named_type,
            SequenceOfType: self.inline_sequenceof_type,
            SetOfType: self.inline_setof_type,
            ValueListType: self.inline_value_list_type,
            ChoiceType: self.inline_constructed_type,
            SequenceType: self.inline_constructed_type,
            SetType: self.inline_constructed_type,
            BitStringType: self.inline_bitstring_type,
        }

    def generate_code(self):
        self.writer.write_line('from pyasn1.type import univ, char, namedtype, namedval, tag, constraint, useful')
        for module in self.referenced_modules:
            if module is not self.sema_module:
                self.writer.write_line('import ' + _sanitize_module(module.name))
        self.writer.write_blanks(2)

        # Generate _OID if sema_module contains any object identifier values.
        oids = [n for n in self.sema_module.descendants() if isinstance(n, ObjectIdentifierValue)]
        if oids:
            self.writer.write_block(self.generate_OID())
            self.writer.write_blanks(2)

        assignment_components = dependency_sort(self.sema_module.assignments)
        for component in assignment_components:
            for assignment in component:
                self.writer.write_block(self.generate_decl(assignment))
                self.writer.write_blanks(2)

            for assignment in component:
                details = self.generate_definition(assignment)
                if details:
                    self.writer.write_block(details)
                    self.writer.write_blanks(2)

    def generate_definition(self, assignment):
        if not isinstance(assignment, (ValueAssignment, TypeAssignment)):
            raise Exception('Unexpected assignment type %s' % assignment.__class__.__name__)

        if isinstance(assignment, ValueAssignment):
            return None  # Nothing to do here.

        assigned_type, type_decl = assignment.type_name, assignment.type_decl
        assigned_type = _translate_type(assigned_type)
        return self.generate_defn(assigned_type, type_decl)

    def generate_decl(self, t):
        generator = self.decl_generators[type(t)]
        return generator(t)

    def generate_expr(self, t):
        generator = self.inline_generators[type(t)]
        return generator(t)

    def generate_defn(self, class_name, t):
        generator = self.defn_generators[type(t)]
        return generator(class_name, t)

    def decl_type_assignment(self, assignment):
        fragment = self.writer.get_fragment()

        assigned_type, type_decl = assignment.type_name, assignment.type_decl

        if isinstance(type_decl, SelectionType):
            type_decl = self.sema_module.resolve_selection_type(type_decl)

        assigned_type = _translate_type(assigned_type)
        base_type = _translate_type(type_decl.type_name)
        fragment.write_line('class %s(%s):' % (assigned_type, base_type))
        fragment.push_indent()
        fragment.write_line('pass')
        fragment.pop_indent()

        return str(fragment)

    def decl_value_assignment(self, assignment):
        assigned_value, type_decl, value = assignment.value_name, assignment.type_decl, assignment.value
        assigned_value = _sanitize_identifier(assigned_value)
        construct_expr = self.build_value_construct_expr(type_decl, value)
        return '%s = %s' % (assigned_value, construct_expr)

    def defn_simple_type(self, class_name, t):
        if t.constraint:
            return '%s.subtypeSpec = %s' % (class_name, self.build_constraint_expr(t.constraint))

        return None

    def defn_defined_type(self, class_name, t):
        return None

    def defn_constructed_type(self, class_name, t):
        fragment = self.writer.get_fragment()

        fragment.write_line('%s.componentType = namedtype.NamedTypes(' % class_name)
        fragment.push_indent()
        fragment.write_block(self.inline_component_types(t.components))
        fragment.pop_indent()
        fragment.write_line(')')

        return str(fragment)

    def defn_tagged_type(self, class_name, t):
        fragment = self.writer.get_fragment()

        implicitness = self.sema_module.resolve_tag_implicitness(t.implicitness, t.type_decl)
        if implicitness == TagImplicitness.IMPLICIT:
            tag_implicitness = 'tagImplicitly'
        elif implicitness == TagImplicitness.EXPLICIT:
            tag_implicitness = 'tagExplicitly'
        else:
            raise Exception('Unexpected implicitness: %s' % implicitness)

        base_type = _translate_type(t.type_decl.type_name)

        fragment.write_line(
            '%s.tagSet = %s.tagSet.%s(%s)' % (class_name, base_type, tag_implicitness, self.build_tag_expr(t)))
        nested_dfn = self.generate_defn(class_name, t.type_decl)
        if nested_dfn:
            fragment.write_line(nested_dfn)

        return str(fragment)

    def defn_selection_type(self, class_name, t):
        return None

    def defn_value_list_type(self, class_name, t):
        fragment = self.writer.get_fragment()

        if t.named_values:
            fragment.write_line('%s.namedValues = namedval.NamedValues(' % class_name)
            fragment.push_indent()

            named_values = ['(\'%s\', %s)' % (v.identifier, v.value) for v in t.named_values if
                            not isinstance(v, ExtensionMarker)]
            fragment.write_enumeration(named_values)

            fragment.pop_indent()
            fragment.write_line(')')

        if t.constraint:
            fragment.write_line('%s.subtypeSpec=%s' % (class_name, self.build_constraint_expr(t.constraint)))

        return str(fragment)

    def inline_bitstring_type(self, t):
        return self.inline_simple_type(t)

    def defn_bitstring_type(self, class_name, t):
        fragment = self.writer.get_fragment()

        if t.named_bits:
            fragment.write_line('%s.namedValues = namedval.NamedValues(' % class_name)
            fragment.push_indent()
            named_bits = ['(\'%s\', %s)' % (b.identifier, b.value) for b in t.named_bits]
            fragment.write_enumeration(named_bits)
            fragment.pop_indent()
            fragment.write_line(')')

        if t.constraint:
            fragment.write_line('%s.subtypeSpec=%s' % (class_name, self.build_constraint_expr(t.constraint)))

        return str(fragment)

    def defn_collection_type(self, class_name, t):
        fragment = self.writer.get_fragment()
        fragment.write_line('%s.componentType = %s' % (class_name, self.generate_expr(t.type_decl)))

        if t.size_constraint:
            fragment.write_line('%s.subtypeSpec=%s' % (class_name, self.build_constraint_expr(t.size_constraint)))

        return str(fragment)

    def inline_simple_type(self, t):
        type_expr = _translate_type(t.type_name) + '()'
        if t.constraint:
            type_expr += '.subtype(subtypeSpec=%s)' % self.build_constraint_expr(t.constraint)

        return type_expr

    def inline_defined_type(self, t):
        translated_type = _translate_type(t.type_name) + '()'
        if t.module_ref and t.module_ref.name != self.sema_module.name:
            translated_type = _sanitize_module(t.module_ref.name) + '.' + translated_type
        return translated_type

    def inline_constructed_type(self, t):
        fragment = self.writer.get_fragment()

        class_name = _translate_type(t.type_name)

        fragment.write_line('%s(componentType=namedtype.NamedTypes(' % class_name)

        fragment.push_indent()
        fragment.write_block(self.inline_component_types(t.components))
        fragment.pop_indent()

        fragment.write_line('))')

        return str(fragment)

    def inline_component_types(self, components):
        fragment = self.writer.get_fragment()

        component_exprs = []
        for c in components:
            if not isinstance(c, ExtensionMarker):
                component_exprs.append(self.generate_expr(c))

        fragment.write_enumeration(component_exprs)

        return str(fragment)

    def inline_tagged_type(self, t):
        implicitness = self.sema_module.resolve_tag_implicitness(t.implicitness, t.type_decl)
        if implicitness == TagImplicitness.IMPLICIT:
            tag_implicitness = 'implicitTag'
        elif implicitness == TagImplicitness.EXPLICIT:
            tag_implicitness = 'explicitTag'
        else:
            raise Exception('Unexpected implicitness: %s' % implicitness)

        type_expr = self.generate_expr(t.type_decl)
        type_expr += '.subtype(%s=%s)' % (tag_implicitness, self.build_tag_expr(t))

        return type_expr

    def inline_selection_type(self, t):
        selected_type = self.sema_module.resolve_selection_type(t)
        if selected_type is None:
            raise Exception('Found no member %s in %s' % (t.identifier, t.type_decl))

        return self.generate_expr(selected_type)

    def build_tag_expr(self, tag_def):
        context = _translate_tag_class(tag_def.class_name)

        tagged_type_decl = self.sema_module.resolve_type_decl(tag_def.type_decl, self.referenced_modules)
        if isinstance(tagged_type_decl, ConstructedType):
            tag_format = 'tag.tagFormatConstructed'
        else:
            tag_format = 'tag.tagFormatSimple'

        return 'tag.Tag(%s, %s, %s)' % (context, tag_format, tag_def.class_number)

    def build_constraint_expr(self, constraint):
        def unpack_size_constraint(nested):
            if isinstance(nested, SingleValueConstraint):
                return self.translate_value(nested.value), self.translate_value(nested.value)
            elif isinstance(nested, ValueRangeConstraint):
                return self.translate_value(nested.min_value), self.translate_value(nested.max_value)
            else:
                raise Exception('Unrecognized nested size constraint type: %s' % nested.__class__.__name__)

        if isinstance(constraint, SingleValueConstraint):
            return 'constraint.SingleValueConstraint(%s)' % (self.translate_value(constraint.value))
        elif isinstance(constraint, SizeConstraint):
            min_value, max_value = unpack_size_constraint(constraint.nested)
            return 'constraint.ValueSizeConstraint(%s, %s)' % (self.translate_value(min_value), self.translate_value(max_value))
        elif isinstance(constraint, ValueRangeConstraint):
            return 'constraint.ValueRangeConstraint(%s, %s)' % (self.translate_value(constraint.min_value),
                                                                self.translate_value(constraint.max_value))
        else:
            raise Exception('Unrecognized constraint type: %s' % constraint.__class__.__name__)

    def build_value_construct_expr(self, type_decl, value):
        """ Build a valid construct-expression for values, depending on
        the target pyasn1 type.
        """

        def build_value_expr(type_name, value):
            """ Special treatment for bstring and hstring values,
            which use different construction depending on target type.
            """
            if isinstance(value, BinaryStringValue):
                if type_name == 'OCTET STRING':
                    return 'binValue=\'%s\'' % value.value
                else:
                    return '"\'%s\'B"' % value.value
            elif isinstance(value, HexStringValue):
                if type_name == 'OCTET STRING':
                    return 'hexValue=\'%s\'' % value.value
                else:
                    return '"\'%s\'H"' % value.value
            else:
                return self.translate_value(value)

        if isinstance(value, ObjectIdentifierValue):
            return self.build_object_identifier_value(value)
        else:
            value_type = _translate_type(type_decl.type_name)
            root_type = self.sema_module.resolve_type_decl(type_decl, self.referenced_modules)
            return '%s(%s)' % (value_type, build_value_expr(root_type.type_name, value))

    def inline_component_type(self, t):
        if t.components_of_type:
            # COMPONENTS OF works like a literal include, so just
            # expand all components of the referenced type.
            included_type_decl = self.sema_module.resolve_type_decl(t.components_of_type, self.referenced_modules)
            included_content = self.inline_component_types(included_type_decl.components)

            # Strip trailing newline from inline_component_types
            # to make the list line up
            return included_content.strip()

        if t.optional:
            return "namedtype.OptionalNamedType('%s', %s)" % (t.identifier, self.generate_expr(t.type_decl))
        elif t.default_value is not None:
            type_expr = self.generate_expr(t.type_decl)
            type_expr += '.subtype(value=%s)' % self.translate_value(t.default_value)

            return "namedtype.DefaultedNamedType('%s', %s)" % (t.identifier, type_expr)
        else:
            return "namedtype.NamedType('%s', %s)" % (t.identifier, self.generate_expr(t.type_decl))

    def inline_named_type(self, t):
        return "namedtype.NamedType('%s', %s)" % (t.identifier, self.generate_expr(t.type_decl))

    def inline_value_list_type(self, t):
        class_name = _translate_type(t.type_name)
        if t.named_values:
            named_values = ['(\'%s\', %s)' % (v.identifier, v.value) for v in t.named_values if
                            not isinstance(v, ExtensionMarker)]
            return '%s(namedValues=namedval.NamedValues(%s))' % (class_name, ', '.join(named_values))
        else:
            return class_name + '()'

    def inline_sequenceof_type(self, t):
        expr = 'univ.SequenceOf(componentType=%s)' % self.generate_expr(t.type_decl)
        if t.size_constraint:
            expr += '.subtype(subtypeSpec=%s)' % \
                    self.build_constraint_expr(t.size_constraint)
        return expr

    def inline_setof_type(self, t):
        expr = 'univ.SetOf(componentType=%s)' % self.generate_expr(t.type_decl)
        if t.size_constraint:
            expr += '.subtype(subtypeSpec=%s)' % \
                    self.build_constraint_expr(t.size_constraint)
        return expr

    def build_object_identifier_value(self, t):
        objid_components = []

        for c in t.components:
            if isinstance(c, NameForm):
                if c.name in REGISTERED_OID_NAMES:
                    objid_components.append(str(REGISTERED_OID_NAMES[c.name]))
                else:
                    objid_components.append(self.translate_value(c.name))
            elif isinstance(c, NumberForm):
                objid_components.append(str(c.value))
            elif isinstance(c, NameAndNumberForm):
                objid_components.append(str(c.number.value))
            else:
                raise Exception('Unexpected component type %s' % c.__class__.__name__)

        return '_OID(%s)' % ', '.join(objid_components)

    def generate_OID(self):
        fragment = self.writer.get_fragment()

        fragment.write_line('def _OID(*components):')
        fragment.push_indent()
        fragment.write_line('output = []')
        fragment.write_line('for x in tuple(components):')
        fragment.push_indent()
        fragment.write_line('if isinstance(x, univ.ObjectIdentifier):')
        fragment.push_indent()
        fragment.write_line('output.extend(list(x))')
        fragment.pop_indent()
        fragment.write_line('else:')
        fragment.push_indent()
        fragment.write_line('output.append(int(x))')
        fragment.pop_indent()
        fragment.pop_indent()
        fragment.write_blanks(1)
        fragment.write_line('return univ.ObjectIdentifier(output)')
        fragment.pop_indent()

        fragment.pop_indent()

        return str(fragment)

    def translate_value(self, value):
        """ Translate ASN.1 built-in values to Python equivalents.
        Unrecognized values are not translated.
        """
        if isinstance(value, ReferencedValue):
            v = _sanitize_identifier(value.name)

            # If this is a cross-module reference, extract the Python module
            # name as a prefix.
            if value.module_ref:
                module = value.module_ref.name
            else:
                module = None

            if module and module != self.sema_module.name:
                v = _sanitize_module(module) + '.' + v
        elif _heuristic_is_identifier(value):
            v = _sanitize_identifier(value)
        else:
            v = value

        return _ASN1_BUILTIN_VALUES.get(v, v)


def generate_pyasn1(sema_module, out_stream, referenced_modules):
    return Pyasn1Backend(sema_module, out_stream, referenced_modules).generate_code()


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
    'ANY': 'univ.Any',
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
    'GraphicString': 'char.GraphicString',
    'GeneralizedTime': 'useful.GeneralizedTime',
    'UTCTime': 'useful.UTCTime',
    'ObjectDescriptor': 'useful.ObjectDescriptor',  # In pyasn1 r1.2
    'VisibleString': 'char.VisibleString',
    'TeletexString': 'char.TeletexString',
    'UniversalString': 'char.UniversalString',
    'BMPString': 'char.BMPString',
    'T61String': 'char.T61String',
    'VideotexString': 'char.VideotexString',
}


def _translate_type(type_name):
    """ Translate ASN.1 built-in types to pyasn1 equivalents.
    Non-builtins are not translated.
    """
    if not isinstance(type_name, str):
        raise Exception('Type name must be a string')
    type_name = _sanitize_identifier(type_name)

    return _ASN1_BUILTIN_TYPES.get(type_name, type_name)


def _translate_tag_class(tag_class):
    """ Translate ASN.1 tag class names to pyasn1 equivalents.
    Defaults to tag.tagClassContext if tag_class is not
    recognized.
    """
    return _ASN1_TAG_CONTEXTS.get(tag_class, 'tag.tagClassContext')


def _heuristic_is_identifier(value):
    """ Return True if this value is likely an identifier.
    """
    first = str(value)[0]
    return first != '-' and not first.isdigit()


def _sanitize_identifier(name):
    """ Sanitize ASN.1 type and value identifiers so that they're
    valid Python identifiers.
    """
    name = str(name)
    name = name.replace('-', '_')
    if name in keyword.kwlist:
        name += '_'

    return name


def _sanitize_module(name):
    """ Sanitize ASN.1 module identifiers so that they're PEP8 compliant identifiers.
    """
    return _sanitize_identifier(name).lower()


# Simplistic command-line driver
def main():
    arg_parser = argparse.ArgumentParser(description='Generate Python classes from an ASN.1 definition file.'
                                                     'Output to stdout by default.')
    arg_parser.add_argument('file', help='the ASN.1 file to process')
    arg_parser.add_argument('--split', action='store_true',
                            help='output multiple modules to separate files')
    args = arg_parser.parse_args()

    with open(args.file, 'r') as data:
        asn1def = data.read()

    parse_tree = parser.parse_asn1(asn1def)

    modules = build_semantic_model(parse_tree)
    if len(modules) > 1 and not args.split:
        print('WARNING: More than one module generated to the same stream.', file=sys.stderr)

    output_file = sys.stdout
    for module in modules:
        try:
            if args.split:
                output_file = open(_sanitize_module(module.name) + '.py', 'w')
            print(pygen.auto_generated_header(args.file, __version__),
                  file=output_file)
            generate_pyasn1(module, output_file, modules)
        finally:
            if output_file != sys.stdout:
                output_file.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
