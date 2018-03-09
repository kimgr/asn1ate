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

import re
from copy import copy
from pyparsing import Keyword, Literal, Word, OneOrMore, ZeroOrMore, Combine, Regex, Forward, Optional, Group, Suppress, \
    delimitedList, cStyleComment, nums, srange, dblQuotedString, Or, CaselessLiteral

__all__ = ['parse_asn1', 'AnnotatedToken']


def parse_asn1(asn1_definition):
    """ Parse a string containing one or more ASN.1 module definitions.
    Returns a list of module syntax trees represented as nested lists of
    AnnotatedToken objects.
    """
    grammar = _build_asn1_grammar()
    parse_result = grammar.parseString(asn1_definition)
    parse_tree = parse_result.asList()
    return parse_tree


def print_parse_tree(node, indent=1):
    """ Debugging aid. Dumps a parse tree as returned
    from parse_asn1 to stdout in indented tree form.
    """

    def indented_print(msg):
        print(' ' * indent + msg)

    if type(node) is AnnotatedToken:
        # tagged token
        tag, values = node.ty, node.elements
        indented_print('%s:' % tag)
        print_parse_tree(values, indent + 1)
    elif type(node) is list:
        # token list
        for token in node:
            print_parse_tree(token, indent + 1)
    else:
        # token
        indented_print(str(node))


class AnnotatedToken(object):
    """ A simple data structure to keep track of a token's
    type, identified by a string, and its children.
    Children may be other annotated tokens, lists or simple
    strings.
    """

    def __init__(self, token_type, elements):
        self.ty = token_type
        self.elements = elements

    def __str__(self):
        return 'T(%s)%s' % (self.ty, self.elements)

    __repr__ = __str__


def _build_asn1_grammar():
    def build_identifier(prefix_pattern):
        identifier_suffix = Optional(Word(srange('[-0-9a-zA-Z]')))
        # todo: more rigorous? trailing hyphens and -- forbidden
        return Combine(Word(srange(prefix_pattern), exact=1) + identifier_suffix)

    def braced_list(element_rule):
        elements_rule = Optional(delimitedList(element_rule))
        return Suppress('{') + Group(elements_rule) + Suppress('}')

    def annotate(name):
        def annotation(t):
            return AnnotatedToken(name, t.asList())

        return annotation

    # Reserved words
    ANY = Keyword('ANY')
    DEFINED_BY = Keyword('DEFINED BY')
    DEFINITIONS = Keyword('DEFINITIONS')
    BEGIN = Keyword('BEGIN')
    END = Keyword('END')
    OPTIONAL = Keyword('OPTIONAL')
    DEFAULT = Keyword('DEFAULT')
    TRUE = Keyword('TRUE')
    FALSE = Keyword('FALSE')
    UNIVERSAL = Keyword('UNIVERSAL')
    APPLICATION = Keyword('APPLICATION')
    PRIVATE = Keyword('PRIVATE')
    MIN = Keyword('MIN')
    MAX = Keyword('MAX')
    IMPLICIT = Keyword('IMPLICIT')
    EXPLICIT = Keyword('EXPLICIT')
    EXPLICIT_TAGS = Keyword('EXPLICIT TAGS')
    IMPLICIT_TAGS = Keyword('IMPLICIT TAGS')
    AUTOMATIC_TAGS = Keyword('AUTOMATIC TAGS')
    EXTENSIBILITY_IMPLIED = Keyword('EXTENSIBILITY IMPLIED')
    COMPONENTS_OF = Keyword('COMPONENTS OF')
    ELLIPSIS = Keyword('...')
    SIZE = Keyword('SIZE')
    OF = Keyword('OF')
    IMPORTS = Keyword('IMPORTS')
    EXPORTS = Keyword('EXPORTS')
    FROM = Keyword('FROM')

    # Built-in types
    SEQUENCE = Keyword('SEQUENCE')
    SET = Keyword('SET')
    CHOICE = Keyword('CHOICE')
    ENUMERATED = Keyword('ENUMERATED')
    BIT_STRING = Keyword('BIT STRING')
    BOOLEAN = Keyword('BOOLEAN')
    REAL = Keyword('REAL')
    OCTET_STRING = Keyword('OCTET STRING')
    CHARACTER_STRING = Keyword('CHARACTER STRING')
    NULL = Keyword('NULL')
    INTEGER = Keyword('INTEGER')
    OBJECT_IDENTIFIER = Keyword('OBJECT IDENTIFIER')

    # Restricted string types
    BMPString = Keyword('BMPString')
    GeneralString = Keyword('GeneralString')
    GraphicString = Keyword('GraphicString')
    IA5String = Keyword('IA5String')
    ISO646String = Keyword('ISO646String')
    NumericString = Keyword('NumericString')
    PrintableString = Keyword('PrintableString')
    TeletexString = Keyword('TeletexString')
    T61String = Keyword('T61String')
    UniversalString = Keyword('UniversalString')
    UTF8String = Keyword('UTF8String')
    VideotexString = Keyword('VideotexString')
    VisibleString = Keyword('VisibleString')

    # Useful types
    GeneralizedTime = Keyword('GeneralizedTime')
    UTCTime = Keyword('UTCTime')
    ObjectDescriptor = Keyword('ObjectDescriptor')

    # Literals
    number = Word(nums)
    signed_number = Combine(Optional('-') + number)  # todo: consider defined values from 18.1
    bstring = Suppress('\'') + StringOf('01') + Suppress('\'B')
    hstring = Suppress('\'') + StringOf('0123456789ABCDEF') + Suppress('\'H')

    # Comments
    hyphen_comment = Regex(r"--[\s\S]*?(--|$)", flags=re.MULTILINE)
    comment = hyphen_comment | cStyleComment

    # identifier
    identifier = build_identifier('[a-z]')

    # references
    # these are duplicated to force unique token annotations
    valuereference = build_identifier('[a-z]')
    typereference = build_identifier('[A-Z]')
    module_reference = build_identifier('[A-Z]')
    reference = valuereference | typereference  # TODO: consider object references from 12.1

    # values
    # todo: consider more literals from 16.9
    boolean_value = TRUE | FALSE
    bitstring_value = bstring | hstring  # todo: consider more forms from 21.9
    integer_value = signed_number
    null_value = NULL
    cstring_value = dblQuotedString

    exponent = CaselessLiteral('e') + signed_number
    real_value = Combine(signed_number + Optional(Literal('.') + Optional(number)) + Optional(exponent))

    # In value range constraints, decimal points must be followed by number, or
    # the grammar becomes ambiguous: ([1.].100) vs ([1]..[100])
    constraint_real_value = Combine(signed_number + Optional(Literal('.') + number) + Optional(exponent))

    builtin_value = boolean_value | bitstring_value | real_value | integer_value | null_value | cstring_value
    external_value_reference = module_reference + Suppress('.') + valuereference
    defined_value = external_value_reference | valuereference  # todo: more options from 13.1
    referenced_value = Unique(defined_value)  # todo: more options from 16.11

    # object identifier value
    name_form = Unique(identifier)
    number_form = Unique(number)
    name_and_number_form = name_form + Suppress('(') + number_form + Suppress(')')
    objid_components = name_and_number_form | name_form | number_form | defined_value
    objid_components_list = OneOrMore(objid_components)
    object_identifier_value = Suppress('{') + \
                              (objid_components_list | (defined_value + objid_components_list)) + \
                              Suppress('}')

    value = builtin_value | referenced_value | object_identifier_value

    # definitive identifier value
    definitive_number_form = Unique(number)
    definitive_name_and_number_form = name_form + Suppress('(') + definitive_number_form + Suppress(')')
    definitive_objid_component = definitive_name_and_number_form | name_form | definitive_number_form
    definitive_objid_component_list = OneOrMore(definitive_objid_component)
    definitive_identifier = Optional(Suppress('{') + definitive_objid_component_list + Suppress('}'))

    # tags
    class_ = UNIVERSAL | APPLICATION | PRIVATE
    class_number = Unique(number)  # todo: consider defined values from 30.1
    tag = Suppress('[') + Optional(class_) + class_number + Suppress(']')
    tag_default = EXPLICIT_TAGS | IMPLICIT_TAGS | AUTOMATIC_TAGS

    # extensions
    extension_default = Unique(EXTENSIBILITY_IMPLIED)

    # values

    # Forward-declare these, they can only be fully defined once
    # we have all types defined. There are some circular dependencies.
    named_type = Forward()
    type_ = Forward()

    # constraints
    # todo: consider the full subtype and general constraint syntax described in 45.*
    lower_bound = (constraint_real_value | signed_number | referenced_value | MIN)
    upper_bound = (constraint_real_value | signed_number | referenced_value | MAX)
    single_value_constraint = Suppress('(') + value + Suppress(')')
    value_range_constraint = Suppress('(') + lower_bound + Suppress('..') + upper_bound + Suppress(')')
    # TODO: Include contained subtype constraint here if we ever implement it.
    size_constraint = Optional(Suppress('(')) + Suppress(SIZE) + (single_value_constraint | value_range_constraint) + Optional(Suppress(')'))

    # types
    # todo: consider other defined types from 13.1
    defined_type = Optional(module_reference + Suppress('.'), default=None) + typereference + Optional(size_constraint, default=None)

    # TODO: consider exception syntax from 24.1
    extension_marker = Unique(ELLIPSIS)

    component_type_optional = named_type + Suppress(OPTIONAL)
    component_type_default = named_type + Suppress(DEFAULT) + value
    component_type_components_of = Suppress(COMPONENTS_OF) + type_
    component_type = component_type_components_of | component_type_optional | component_type_default | named_type

    tagged_type = tag + Optional(IMPLICIT | EXPLICIT, default=None) + type_

    named_number_value = Suppress('(') + signed_number + Suppress(')')
    named_number = identifier + named_number_value
    named_nonumber = Unique(identifier)
    enumeration = named_number | named_nonumber

    set_type = SET + braced_list(component_type | extension_marker)
    sequence_type = SEQUENCE + braced_list(component_type | extension_marker)
    sequenceof_type = Suppress(SEQUENCE) + Optional(size_constraint, default=None) + Suppress(OF) + (type_ | named_type)
    setof_type = Suppress(SET) + Optional(size_constraint, default=None) + Suppress(OF) + (type_ | named_type)
    choice_type = CHOICE + braced_list(named_type | extension_marker)
    selection_type = identifier + Suppress('<') + type_
    enumerated_type = ENUMERATED + braced_list(enumeration | extension_marker)
    bitstring_type = BIT_STRING + Optional(braced_list(named_number), default=[]) + Optional(single_value_constraint | size_constraint, default=None)
    plain_integer_type = INTEGER
    restricted_integer_type = INTEGER + braced_list(named_number) + Optional(single_value_constraint, default=None)
    boolean_type = BOOLEAN
    real_type = REAL
    null_type = NULL
    object_identifier_type = OBJECT_IDENTIFIER
    octetstring_type = OCTET_STRING + Optional(size_constraint)
    unrestricted_characterstring_type = CHARACTER_STRING
    restricted_characterstring_type = BMPString | GeneralString | \
                                      GraphicString | IA5String | \
                                      ISO646String | NumericString | \
                                      PrintableString | TeletexString | \
                                      T61String | UniversalString | \
                                      UTF8String | VideotexString | \
                                      VisibleString
    characterstring_type = (restricted_characterstring_type | unrestricted_characterstring_type) + Optional(size_constraint)
    useful_type = GeneralizedTime | UTCTime | ObjectDescriptor

    # ANY type
    any_type = ANY + Optional(Suppress(DEFINED_BY + identifier))

    # todo: consider other builtins from 16.2
    simple_type = (any_type | boolean_type | null_type | octetstring_type | characterstring_type | real_type | plain_integer_type | object_identifier_type | useful_type) + Optional(value_range_constraint | single_value_constraint)
    constructed_type = choice_type | sequence_type | set_type
    value_list_type = restricted_integer_type | enumerated_type
    builtin_type = value_list_type | tagged_type | simple_type | constructed_type | sequenceof_type | setof_type | bitstring_type

    referenced_type = defined_type | selection_type  # todo: consider other ref:d types from 16.3

    type_ << (builtin_type | referenced_type)
    named_type << (identifier + type_)

    type_assignment = typereference + '::=' + type_
    value_assignment = valuereference + type_ + '::=' + value

    assignment = type_assignment | value_assignment
    assignment_list = ZeroOrMore(assignment)

    # TODO: Maybe handle full assigned-identifier syntax with defined values
    # described in 12.1, but I haven't been able to find examples of it, and I
    # can't say for sure what acceptable syntax is.
    global_module_reference = module_reference + Optional(object_identifier_value, default=None)

    symbol = Unique(reference)  # TODO: parameterized reference?
    symbol_list = delimitedList(symbol, delim=',')
    symbols_from_module = Group(Group(symbol_list) + Suppress(FROM) + global_module_reference)
    symbols_from_module_list = OneOrMore(symbols_from_module)
    symbols_imported = Unique(symbols_from_module_list)
    exports = Suppress(EXPORTS) + Optional(symbol_list) + Suppress(';')
    imports = Suppress(IMPORTS) + Optional(symbols_imported) + Suppress(';')

    module_body = Optional(exports, default=None) + Optional(imports, default=None) + assignment_list
    module_identifier = module_reference + definitive_identifier
    module_definition = module_identifier + Suppress(DEFINITIONS) + Optional(tag_default, default=None) + \
                        Optional(extension_default, default=None) + Suppress('::=') + \
                        Suppress(BEGIN) + module_body + Suppress(END)

    module_definition.ignore(comment)

    # Mark up the parse results with token tags
    identifier.setParseAction(annotate('Identifier'))
    named_number_value.setParseAction(annotate('Value'))
    tag.setParseAction(annotate('Tag'))
    class_.setParseAction(annotate('TagClass'))
    class_number.setParseAction(annotate('TagClassNumber'))
    type_.setParseAction(annotate('Type'))
    simple_type.setParseAction(annotate('SimpleType'))
    choice_type.setParseAction(annotate('ChoiceType'))
    sequence_type.setParseAction(annotate('SequenceType'))
    set_type.setParseAction(annotate('SetType'))
    value_list_type.setParseAction(annotate('ValueListType'))
    bitstring_type.setParseAction(annotate('BitStringType'))
    sequenceof_type.setParseAction(annotate('SequenceOfType'))
    setof_type.setParseAction(annotate('SetOfType'))
    named_number.setParseAction(annotate('NamedValue'))
    named_nonumber.setParseAction(annotate('NamedValue'))
    single_value_constraint.setParseAction(annotate('SingleValueConstraint'))
    size_constraint.setParseAction(annotate('SizeConstraint'))
    value_range_constraint.setParseAction(annotate('ValueRangeConstraint'))
    component_type.setParseAction(annotate('ComponentType'))
    component_type_optional.setParseAction(annotate('ComponentTypeOptional'))
    component_type_default.setParseAction(annotate('ComponentTypeDefault'))
    component_type_components_of.setParseAction(annotate('ComponentTypeComponentsOf'))
    tagged_type.setParseAction(annotate('TaggedType'))
    named_type.setParseAction(annotate('NamedType'))
    type_assignment.setParseAction(annotate('TypeAssignment'))
    value_assignment.setParseAction(annotate('ValueAssignment'))
    module_reference.setParseAction(annotate('ModuleReference'))
    global_module_reference.setParseAction(annotate('GlobalModuleReference'))
    module_body.setParseAction(annotate('ModuleBody'))
    module_definition.setParseAction(annotate('ModuleDefinition'))
    extension_marker.setParseAction(annotate('ExtensionMarker'))
    name_form.setParseAction(annotate('NameForm'))
    number_form.setParseAction(annotate('NumberForm'))
    name_and_number_form.setParseAction(annotate('NameAndNumberForm'))
    object_identifier_value.setParseAction(annotate('ObjectIdentifierValue'))
    definitive_identifier.setParseAction(annotate('DefinitiveIdentifier'))
    definitive_number_form.setParseAction(annotate('DefinitiveNumberForm'))
    definitive_name_and_number_form.setParseAction(annotate('DefinitiveNameAndNumberForm'))
    exports.setParseAction(annotate('Exports'))
    imports.setParseAction(annotate('Imports'))
    assignment_list.setParseAction(annotate('AssignmentList'))
    bstring.setParseAction(annotate('BinaryStringValue'))
    hstring.setParseAction(annotate('HexStringValue'))
    defined_type.setParseAction(annotate('DefinedType'))
    selection_type.setParseAction(annotate('SelectionType'))
    referenced_value.setParseAction(annotate('ReferencedValue'))

    start = OneOrMore(module_definition)
    return start


def Unique(token):
    """ Use to create a distinct name of a production
    with the same form as another, e.g.
      identifier = build_identifier('[a-z]')
      valuereference = build_identifier('[a-z]')
    We prefer:
      identifier = build_identifier('[a-z]')
      valuereference = Unique(identifier)
    to avoid duplicating the details of the grammar.
    This allows unique parse actions for productions
    with the same underlying rules.
    """
    return copy(token)


def StringOf(elements):
    """ Create a rule to parse a string of any of the chars in elements.
    Skips any whitespace.
    This is useful for the ASN.1 hstring and bstring productions.
    """
    element = CharSet(elements)
    return Combine(OneOrMore(element), adjacent=False)  # Use adjacent=False to skip whitespace


def CharSet(elements):
    """ Create a set of valid characters as a single rule.
    elements is a string containing all the desired chars, e.g.
      CharSet('01234567890')        # all numbers
      CharSet('01234567890ABCDEF')  # all hex numbers
    """
    unpacked_chars = [Literal(c) for c in elements]
    return Or(unpacked_chars)
