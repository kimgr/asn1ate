#!/usr/bin/python
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
# From: Rick van Rein <rick@openfortress.nl>


import sys
import os.path

from asn1ate import parser
from asn1ate.sema import * 


def toCsym (name):
	"""Replace unsupported characters in ASN.1 symbol names"""
	return str (name).replace (' ', '_').replace ('-', '_')


class QuickDERgen ():
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

	def __init__ (ik, semamod, outfn, refmods):
		ik.semamod = semamod
		ik.refmods = refmods
		if outfn [-2:] == '.h':
			raise Exception ('File cannot overwrite itself -- use another extension than .h for input files')
		ik.unit = toCsym (outfn.rsplit ('.', 1) [0])
		ik.outfile = open (ik.unit + '.h', 'w')
		ik.wout = ik.outfile.write
		# Setup function maps
		ik.ovly_funmap = {
			DefinedType: ik.ovlyDefinedType,
			TypeAssignment: ik.ovlyTypeAssignment,
			TaggedType: ik.ovlyTaggedType,
			SimpleType: ik.ovlySimpleType,
			SequenceType: ik.ovlyConstructedType,
			SetType: ik.ovlyConstructedType,
			ChoiceType: ik.ovlyConstructedType,
			SequenceOfType: ik.ovlySimpleType,	# var sized
			SetOfType: ik.ovlySimpleType,		# var sized
		}
		ik.pack_funmap = {
			DefinedType: ik.packDefinedType,
			TypeAssignment: ik.packTypeAssignment,
			TaggedType: ik.packTaggedType,
			SimpleType: ik.packSimpleType,
			SequenceType: ik.packSequenceType,
			SetType: ik.packSetType,
			ChoiceType: ik.packChoiceType,
			SequenceOfType: ik.packSequenceOfType,
			SetOfType: ik.packSetOfType,
		}

	def newcomma (ik, comma, firstcomma=''):
		ik.comma0 = firstcomma
		ik.comma1 = comma

	def comma (ik):
		ik.wout (ik.comma0)
		ik.comma0 = ik.comma1

	def close (ik):
		ik.outfile.close ()

	def generate_head (ik):
		ik.wout ('/*\n * asn2quickder output for ' + ik.semamod.name + ' -- automatically generated\n *\n * For information on Quick `n\' Easy DER, see https://github.com/vanrein/quick-der\n *\n */\n\n\n#include <quick-der/api.h>\n\n\n')
		ik.wout ('/* This module ' + toCsym (ik.semamod.name) + ' depends on:\n')
		for rm in ik.refmods:
			ik.wout (' *   ' + toCsym (rm.name) + '\n')
		if len (ik.refmods) == 0:
			ik.wout (' *   (no other modules)\n')
		ik.wout (' */\n\n')

	def generate_tail (ik):
		ik.wout ('\n\n/* asn2quickder output for ' + ik.semamod.name + ' ends here */\n')

	def generate_ovly (ik):
		ik.wout ('\n\n/* Overlay structures with ASN.1 derived nesting and labelling */\n\n')
		for node in ik.semamod.assignments:
			ik.generate_ovly_node (node)

	def generate_pack (ik):
		ik.wout ('\n\n/* Parser definitions in terms of ASN.1 derived bytecode instructions */\n\n')
		for node in ik.semamod.assignments:
			tnm = type (node)
			if tnm in ik.pack_funmap:
				ik.pack_funmap [tnm] (node)
			else:
				print 'No pack generator for ' + str (tnm)

	def generate_ovly_node (ik, node):
		tnm = type (node)
		if tnm in ik.ovly_funmap:
			ik.ovly_funmap [tnm] (node)
		else:
			print 'No overlay generator for ' + str (tnm)

	def generate_pack_node (ik, node):
		tnm = type (node)
		if tnm in ik.pack_funmap:
			ik.pack_funmap [tnm] (node)
		else:
			print 'No pack generator for ' + str (tnm)


	def ovlyTypeAssignment (ik, node):
		ik.wout ('typedef ')
		ik.generate_ovly_node (node.type_decl)
		ik.wout (' ' + ik.unit + '_' + toCsym (node.type_name) + '_ovly;\n\n')

	def packTypeAssignment (ik, node):
		ik.wout ('#define DER_PACK_' + ik.unit + '_' + toCsym (node.type_name))
		ik.newcomma (', \\\\\n\t', ' \\\\\n\t')
		ik.generate_pack_node (node.type_decl)
		ik.wout ('\n\n')

	def ovlyDefinedType (ik, node):
		mod = node.module_name or ik.unit
		ik.wout (toCsym (mod) + '_' + toCsym (node.type_name) + '_ovly')

	def packDefinedType (ik, node):
		mod = node.module_name or ik.unit
		ik.comma ()
		ik.wout ('DER_PACK_' + toCsym (mod) + '_' + toCsym (node.type_name))

	def ovlySimpleType (ik, node):
		ik.wout ('dercursor')

	def packSimpleType (ik, node):
		ik.comma ()
		ik.wout ('DER_PACK_STORE | DER_TAG_' + node.type_name.replace (' ', '_').upper ())

	def ovlyTaggedType (ik, node):
		# tag = str (node) 
		# tag = tag [:tag.find (']')] + ']'
		# ik.wout ('/* ' + tag + ' */ ')
		# if node.implicity == TagImplicity.IMPLICIT:
		# 	tag = tag + ' IMPLICIT'
		# elif node.implicity == TagImplicity.IMPLICIT:
		# 	tag = tag + ' EXPLICIT'
		ik.generate_ovly_node (node.type_decl)

	def packTaggedType (ik, node):
		#TODO# Need to push down node.implicity == TagImplicity.IMPLICIT
		#TODO# Need to process tag class
		ik.comma ()
		ik.wout ('DER_PACK_ENTER | DER_' + (node.class_name or 'CONTEXT') + '_TAG(' + node.class_number + ')')
		ik.generate_pack_node (node.type_decl)
		ik.comma ()
		ik.wout ('DER_PACK_LEAVE')

	# Sequence, Set, Choice
	def ovlyConstructedType (ik, node):
		ik.wout ('struct {\n');
		for comp in node.components:
			ik.wout ('\t')
			ik.generate_ovly_node (comp.type_decl)
			ik.wout (' ' + toCsym (comp.identifier) + '; -- ' + str (comp.type_decl) + '\n')
		ik.wout ('}')

	def packSequenceType (ik, node):
		ik.comma ()
		ik.wout ('DER_PACK_ENTER | DER_TAG_SEQUENCE')
		for comp in node.components:
			if comp.optional:
				ik.comma ()
				ik.wout ('DER_PACK_OPTIONAL')
			ik.generate_pack_node (comp.type_decl)
		ik.comma ()
		ik.wout ('DER_PACK_LEAVE')

	def packSetType (ik, node):
		ik.comma ()
		ik.wout ('DER_PACK_ENTER | DER_TAG_SET')
		for comp in node.components:
			if comp.optional:
				ik.comma ()
				ik.wout ('DER_PACK_OPTIONAL')
			ik.generate_pack_node (comp.type_decl)
		ik.comma ()
		ik.wout ('DER_PACK_LEAVE')

	def packChoiceType (ik, node):
		ik.comma ()
		ik.wout ('DER_TAG_CHOICE_BEGIN')
		for comp in node.components:
			if comp.optional:
				ik.comma ()
				ik.wout ('DER_PACK_OPTIONAL')
			ik.generate_pack_node (comp.type_decl)
		ik.comma ()
		ik.wout ('DER_TAG_CHOICE_BEGIN')

	def packSequenceOfType (ik, node):
		ik.comma ()
		ik.wout ('DER_TAG_STORE | DER_TAG_SEQUENCE')

	def packSetOfType (ik, node):
		ik.comma ()
		ik.wout ('DER_TAG_STORE | DER_TAG_SEQUENCE')


"""The main program asn2quickder is called with one or more .asn1 files,
   the first of which is mapped to a C header file and the rest is
   loaded to fulfil dependencies.
"""

if len (sys.argv) < 2:
	sys.stderr.write ('Usage: %s main[.asn1] dependency[.asn1]...\n'
		% sys.argv [0])
	sys.exit (1)

mods = []
for file in sys.argv [1:]:
	print 'Parsing', file
	asn1fh = open (file, 'r')
	asn1txt = asn1fh.read ()
	asn1fh.close ()
	asn1tree = parser.parse_asn1 (asn1txt)
	print 'Building semantic model for', file
	asn1sem = build_semantic_model (asn1tree)
	mods.insert (0, asn1sem [0])
	print 'Realised semantic model for', file

cogen = QuickDERgen (mods [-1], os.path.basename (sys.argv [1]), mods [1:])

cogen.generate_head ()
cogen.generate_ovly ()
cogen.generate_pack ()
cogen.generate_tail ()

cogen.close ()


