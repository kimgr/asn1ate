#!/usr/bin/env python
#
# asn2quickder -- Generate header files for C for use with Quick `n' Easy DER
#
# This program owes a lot to asn1ate, which was built to generate pyasn1
# classes, but which was so well-written that it could be extended with a
# code generator for Quick DER.
#
# Much of the code below is diagonally inspired on the pyasn1 backend, so
# a very big thank you to Schneider Electric Buildings AB for helping to
# make this program possible!
#
# Copyright 2016 InternetWide.org and the ARPA2.net project.


import sys
import os.path

from asn1ate import parser
from asn1ate.sema import * 


def toCsym (name):
    """Replace unsupported characters in ASN.1 symbol names"""
    return str(name).replace(' ', '').replace('-', '_')


class QuickDERgen():
    """Generate the C header files for Quick DER, a.k.a. Quick and Easy DER.

       There are two things that are generated for each of the ASN.1 syntax
       declaration symbol of a unit:

       #define DER_PACK_unit_SyntaxDeclSym \
            DER_PACK_ENTER | ..., \
            ... \
            DER_PACK_LEAVE, \
            DER_PACK_END

       this is a walking path for the der_pack() and der_unpack() instructions.
       In addition, there will be a struct for each of the symbols:

       struct unit_SyntaxDeclSym_ovly {
           dercursor field1;
           dercursor field2;
           struct unit_EmbeddedSym_ovly field3;
           dercursor field4;
       };

       The unit prefix will be set to the filename of the module, usually
       something like rfc5280 when the parsed file is rfc5280.asn1 and the
       output is then written to rfc5280.h for easy inclusion by the C code.
    """

    def __init__(self, semamod, outfn, refmods):
        self.semamod = semamod
        self.refmods = refmods
        if outfn [-2:] == '.h':
            raise Exception('File cannot overwrite itself -- use another extension than .h for input files')
        self.unit = toCsym(outfn.rsplit('.', 1) [0])
        self.outfile = open(self.unit + '.h', 'w')
        self.wout = self.outfile.write
        # Setup function maps
        self.ovly_funmap = {
            DefinedType: self.ovlyDefinedType,
            ValueAssignment: self.ignore_node,
            TypeAssignment: self.ovlyTypeAssignment,
            TaggedType: self.ovlyTaggedType,
            SimpleType: self.ovlySimpleType,
            BitStringType: self.ovlySimpleType,
            ValueListType: self.ovlySimpleType,
            SequenceType: self.ovlyConstructedType,
            SetType: self.ovlyConstructedType,
            ChoiceType: self.ovlyConstructedType,
            SequenceOfType: self.ovlySimpleType,    # var sized
            SetOfType: self.ovlySimpleType,         # var sized
            ComponentType: self.ovlySimpleType,  #TODO#
        }
        self.pack_funmap = {
            DefinedType: self.packDefinedType,
            ValueAssignment: self.ignore_node,
            TypeAssignment: self.packTypeAssignment,
            TaggedType: self.packTaggedType,
            SimpleType: self.packSimpleType,
            BitStringType: self.packSimpleType,
            ValueListType: self.ovlySimpleType,
            SequenceType: self.packSequenceType,
            SetType: self.packSetType,
            ChoiceType: self.packChoiceType,
            SequenceOfType: self.packSequenceOfType,
            SetOfType: self.packSetOfType,
            ComponentType: self.packSimpleType,  #TODO#
        }

    def newcomma(self, comma, firstcomma=''):
        self.comma0 = firstcomma
        self.comma1 = comma

    def comma(self):
        self.wout(self.comma0)
        self.comma0 = self.comma1

    def close(self):
        self.outfile.close()

    def generate_head(self):
        self.wout('/*\n * asn2quickder output for ' + self.semamod.name + ' -- automatically generated\n *\n * For information on Quick `n\' Easy DER, see https://github.com/vanrein/quick-der\n *\n * For information on the code generator, see https://github.com/vanrein/asn2quickder\n *\n */\n\n\n#include <quick-der/api.h>\n\n\n')
        closer = ''
        for rm in self.semamod.imports.module2symbols.keys():
            rmfn = toCsym(rm.rsplit('.', 1) [0]).lower()
            self.wout('#include <quick-der/' + rmfn + '.h>\n')
            closer = '\n\n'
        self.wout(closer)
        closer = ''
        for rm in self.semamod.imports.module2symbols.keys():
            rmfn = toCsym(rm.rsplit('.', 1) [0]).lower()
            for sym in self.semamod.imports.module2symbols [rm]:
                self.wout('typedef DER_OVLY_' + toCsym(rmfn) + '_' + toCsym(sym) + ' DER_OVLY_' + toCsym(self.unit) + '_' + toCsym(sym) + ';\n')
                closer = '\n\n'
        self.wout(closer)
        closer = ''
        for rm in self.semamod.imports.module2symbols.keys():
            rmfn = toCsym(rm.rsplit('.', 1) [0]).lower()
            for sym in self.semamod.imports.module2symbols [rm]:
                self.wout('#define DER_PACK_' + toCsym(self.unit) + '_' + toCsym(sym) + ' DER_PACK_' + toCsym(rmfn) + '_' + toCsym(sym) + '\n')
                closer = '\n\n'
        self.wout(closer)

    def generate_tail(self):
        self.wout('\n\n/* asn2quickder output for ' + self.semamod.name + ' ends here */\n')

    def generate_ovly(self):
        self.wout('\n\n/* Overlay structures with ASN.1 derived nesting and labelling */\n\n')
        for assigncompos in dependency_sort(self.semamod.assignments):
            for assign in assigncompos:
                self.generate_ovly_node(assign)

    def generate_pack(self):
        self.wout('\n\n/* Parser definitions in terms of ASN.1 derived bytecode instructions */\n\n')
        for assigncompos in dependency_sort(self.semamod.assignments):
            for assign in assigncompos:
                tnm = type(assign)
                if tnm in self.pack_funmap:
                    self.pack_funmap [tnm](assign)
                else:
                    print 'No pack generator for ' + str(tnm)

    def generate_ovly_node(self, node):
        tnm = type(node)
        if tnm in self.ovly_funmap:
            self.ovly_funmap [tnm](node)
        else:
            print('No overlay generator for ' + str(tnm))
            raise Exception('RAISED WHERE?')

    def generate_pack_node(self, node):
        tnm = type(node)
        if tnm in self.pack_funmap:
            self.pack_funmap [tnm](node)
        else:
            print('No pack generator for ' + str(tnm))

    def ignore_node(self, node):
        pass

    def ovlyTypeAssignment(self, node):
        self.wout('typedef ')
        self.generate_ovly_node(node.type_decl)
        self.wout(' DER_OVLY_' + self.unit + '_' + toCsym(node.type_name) + ';\n\n')

    def packTypeAssignment(self, node):
        self.wout('#define DER_PACK_' + self.unit + '_' + toCsym(node.type_name))
        self.newcomma(', \\\n\t', ' \\\n\t')
        self.generate_pack_node(node.type_decl)
        self.wout('\n\n')

    def ovlyDefinedType(self, node):
        mod = node.module_name or self.unit
        self.wout('DER_OVLY_' + toCsym(mod) + '_' + toCsym(node.type_name))

    def packDefinedType(self, node):
        mod = node.module_name or self.unit
        self.comma()
        self.wout('DER_PACK_' + toCsym(mod) + '_' + toCsym(node.type_name))

    def ovlySimpleType(self, node):
        self.wout('dercursor')

    def packSimpleType(self, node):
        self.comma()
        self.wout('DER_PACK_STORE | DER_TAG_' + node.type_name.replace(' ', '').upper())

    def ovlyTaggedType(self, node):
        # tag = str(node) 
        # tag = tag [:tag.find(']')] + ']'
        # self.wout('/* ' + tag + ' */ ')
        # if node.implicity == TagImplicity.IMPLICIT:
        #     tag = tag + ' IMPLICIT'
        # elif node.implicity == TagImplicity.IMPLICIT:
        #     tag = tag + ' EXPLICIT'
        self.generate_ovly_node(node.type_decl)

    def packTaggedType(self, node):
        #TODO# Need to push down node.implicity == TagImplicity.IMPLICIT
        #TODO# Need to process tag class
        self.comma()
        self.wout('DER_PACK_ENTER | DER_TAG_' +(node.class_name or 'CONTEXT') + '(' + node.class_number + ')')
        self.generate_pack_node(node.type_decl)
        self.comma()
        self.wout('DER_PACK_LEAVE')

    # Sequence, Set, Choice
    def ovlyConstructedType(self, node):
        self.wout('struct {\n');
        for comp in node.components:
            if isinstance(comp, ExtensionMarker):
                self.wout('\t/* ...extensions... */\n')
                continue
            if isinstance(comp, ComponentType) and comp.components_of_type is not None:
                self.wout('\t/* TODO: COMPONENTS OF TYPE ' + str(comp.components_of_type) + ' */\n')
                continue
            self.wout('\t')
            self.generate_ovly_node(comp.type_decl)
            self.wout(' ' + toCsym(comp.identifier) + '; // ' + str(comp.type_decl) + '\n')
        self.wout('}')

    def packSequenceType(self, node):
        self.comma()
        self.wout('DER_PACK_ENTER | DER_TAG_SEQUENCE')
        for comp in node.components:
            if isinstance(comp, ExtensionMarker):
                self.comma()
                self.wout('/* ...ASN.1 extensions... */')
                continue
            if comp.optional:
                self.comma()
                self.wout('DER_PACK_OPTIONAL')
            if comp.type_decl is not None:
                # TODO: None would be due to components_of_type
                self.generate_pack_node(comp.type_decl)
        self.comma()
        self.wout('DER_PACK_LEAVE')

    def packSetType(self, node):
        self.comma()
        self.wout('DER_PACK_ENTER | DER_TAG_SET')
        for comp in node.components:
            if isinstance(comp, ExtensionMarker):
                self.comma()
                self.wout('/* ...extensions... */')
                continue
            if comp.optional:
                self.comma()
                self.wout('DER_PACK_OPTIONAL')
            if comp.type_decl is not None:
                # TODO: None would be due to components_of_type
                self.generate_pack_node(comp.type_decl)
        self.comma()
        self.wout('DER_PACK_LEAVE')

    def packChoiceType(self, node):
        self.comma()
        self.wout('DER_PACK_CHOICE_BEGIN')
        for comp in node.components:
            if isinstance(comp, ExtensionMarker):
                self.comma()
                self.wout('/* ...extensions... */')
                continue
            if comp.type_decl is not None:
                # TODO: None would be due to components_of_type
                self.generate_pack_node(comp.type_decl)
        self.comma()
        self.wout('DER_PACK_CHOICE_END')

    def packSequenceOfType(self, node):
        self.comma()
        self.wout('DER_PACK_STORE | DER_TAG_SEQUENCE')

    def packSetOfType(self, node):
        self.comma()
        self.wout('DER_PACK_STORE | DER_TAG_SEQUENCE')


"""The main program asn2quickder is called with one or more .asn1 files,
   the first of which is mapped to a C header file and the rest is
   loaded to fulfil dependencies.
"""

if len(sys.argv) < 2:
    sys.stderr.write('Usage: %s main[.asn1] dependency[.asn1]...\n'
        % sys.argv [0])
    sys.exit(1)

mods = []
for file in sys.argv [1:]:
    print('Parsing', file)
    with open(file, 'r') as asn1fh:
        asn1tree = parser.parse_asn1(asn1fh.read())
    asn1tree = parser.parse_asn1(asn1txt)
    print('Building semantic model for', file)
    asn1sem = build_semantic_model(asn1tree)
    mods.insert(0, asn1sem [0])
    print('Realised semantic model for', file)

cogen = QuickDERgen(mods [-1], os.path.basename(sys.argv [1]), mods [1:])

cogen.generate_head()
cogen.generate_ovly()
cogen.generate_pack()
cogen.generate_tail()

cogen.close()
