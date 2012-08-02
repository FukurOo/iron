from __future__ import with_statement
import os
import sys

from parse import LibrarySource, Parameter
import c


def generate(cm_path, args):
    interface_path = args[0]

    library = LibrarySource(cm_path)

    with open(interface_path, 'w') as opencmiss_i:
        write_interface(library, opencmiss_i)


def write_interface(library, output):
    """Write SWIG interface file for OpenCMISS

    Arguments:
    library -- parsed library object
    output -- File to write to
    """

    output.write("/*\n * opencmiss.i. This file is automatically generated "
        "from opencmiss.f90.\n * Do not edit this file directly, instead edit "
        "opencmiss.f90 or the generate_bindings script\n */\n")
    output.write(c.C_DEFINES)

    for o in library.ordered_objects:
        if isinstance(o, c.Subroutine):
            (start_lines, end_lines) = routine_swig_lines(o)
            output.write(start_lines)
            output.write(c.subroutine_to_c_header(o))
            output.write(end_lines)
        elif isinstance(o, c.Constant):
            output.write(c.constant_to_c_header(o))
        elif isinstance(o, c.Type):
            output.write(c.type_to_c_header(o))


def routine_swig_lines(routine):
    """Return lines used before and after subroutine for SWIG interfaces
    """
    start_lines = []
    end_lines = []

    if routine.name.endswith('_Initialise'):
        type = routine.name[0:-len('_Initialise')] + 'Type'
        name = routine.parameters[0].name
        start_lines.append(
            '%%apply CMISSDummyInitialiseType *CMISSDummy{%s *%s};' %
            (type, name))
        end_lines.append('%%clear %s *%s;' % (type, name))
    elif routine.name.endswith('_Finalise'):
        type = routine.name[0:-len('_Finalise')] + 'Type'
        name = routine.parameters[0].name
        start_lines.append(
            '%%apply CMISSDummyFinaliseType *CMISSDummy{%s *%s};'
            % (type, name))
        end_lines.append('%%clear %s *%s;' % (type, name))

    for param in routine.parameters:
        (p_start, p_end) = parameter_swig_lines(param)
        if p_start:
            start_lines.append(p_start)
        if p_end:
            end_lines.append(p_end)

    start_lines = '\n'.join(start_lines)
    end_lines = '\n'.join(end_lines)
    if start_lines:
        start_lines = '\n' + start_lines
    if end_lines:
        end_lines = end_lines + '\n'
    return (start_lines, end_lines)


def parameter_swig_lines(parameter):
    typemap = apply_to = ''
    properties = {
        'name': parameter.name,
        'type': c.PARAMETER_CTYPES[parameter.var_type],
    }
    if parameter.pointer and parameter.array_dims == 1:
        # Passing a pointer to an array, to access data allocated
        # internally by OpenCMISS
        if parameter.intent == 'OUT':
            typemap = 'int *DIM1, %(type)s **ARGOUTVIEW_ARRAY1' % properties
            apply_to = ('int *%(name)sSize, %(type)s **%(name)s' %
                properties)
        elif parameter.intent == 'INOUT':
            # Not yet implemented.
            pass
    elif parameter.intent == 'OUT':
        if parameter.array_dims == parameter.required_sizes == 1:
            if parameter.var_type == Parameter.CHARACTER:
                typemap = 'const int Size, char *DummyOutputString'
                apply_to = ('const int %(name)sSize, char *%(name)s' %
                    properties)
            else:
                typemap = ('const int DIM1, %(type)s *ARGOUT_ARRAY1' %
                    properties)
                apply_to = ('const int %(name)sSize, %(type)s *%(name)s' %
                    properties)
        elif parameter.array_dims == 1 and parameter.required_sizes == 0:
            properties.update({"dim": int(parameter.array_spec[0])})
            typemap = '%(type)s ARGOUT_ARRAY1[ANY]' % properties
            apply_to = '%(type)s %(name)s[%(dim)d]' % properties
        elif parameter.array_dims == parameter.required_sizes == 2:
            if parameter.var_type in (Parameter.INTEGER, Parameter.FLOAT,
                    Parameter.DOUBLE):
                typemap = ('const int DIM1, const int DIM2, '
                    '%(type)s *ARGOUT_FARRAY2' % properties)
                apply_to = ('const int %(name)sSize1, '
                    'const int %(name)sSize2, %(type)s *%(name)s' % properties)
        elif parameter.array_dims > 1:
            sys.stderr.write("Error: Output of array with known sizes and "
                "dimensions > 1 not implemented\n")
        elif parameter.array_dims > 2:
            sys.stderr.write("Error: Output of array with dimensions > 1 not "
                "implemented\n")
        elif parameter.var_type != Parameter.CUSTOM_TYPE:
            # Output of scalar value
            typemap = '%(type)s *DummyOutputScalar' % properties
            apply_to = '%(type)s *%(name)s' % properties
    else:
        # Input parameter
        if parameter.var_type == Parameter.CHARACTER:
            if parameter.array_dims == 1:
                typemap = 'const int Size, const char *DummyInputString'
                apply_to = ('const int %(name)sSize, const char *%(name)s' %
                    properties)
            else:
                typemap = ('const int NumStrings, const int StringLength, '
                    'const char *DummyStringList')
                apply_to = ('const int %(name)sNumStrings, '
                    'const int %(name)sStringLength, '
                    'const char *%(name)s' % properties)
        elif parameter.array_dims == parameter.required_sizes == 1:
            if parameter.var_type == Parameter.CUSTOM_TYPE:
                properties.update({"type_name": parameter.type_name})
                typemap = ('const int ArraySize, '
                    'const CMISSDummyType *DummyTypes')
                apply_to = ('const int %(name)sSize, '
                    'const %(type_name)s *%(name)s' % properties)
            else:
                typemap = ('const int DIM1, const %(type)s *IN_ARRAY1' %
                    properties)
                apply_to = ('const int %(name)sSize, const %(type)s *%(name)s'
                    % properties)
        elif parameter.array_dims == 1 and parameter.required_sizes == 0:
            sys.stderr.write("Error: Input of array of known size is not "
                "implemented\n")
        elif parameter.array_dims == 2 and parameter.required_sizes == 2:
            if (parameter.var_type in
                    (Parameter.INTEGER, Parameter.DOUBLE, Parameter.FLOAT)):
                typemap = ('const int DIM1, const int DIM2, '
                    'const %(type)s *IN_FARRAY2' % properties)
                apply_to = ('const int %(name)sSize1, const int '
                    '%(name)sSize2, const %(type)s *%(name)s' % properties)
        elif parameter.array_dims == 2 and parameter.required_sizes < 2:
            sys.stderr.write("Error: Input of 2D array with known dimension "
                "is not implemented\n")
        elif parameter.array_dims > 2:
            sys.stderr.write("Error: Input of array with dimensions > 1 not "
                "implemented\n")
        elif parameter.var_type == Parameter.LOGICAL:
            typemap = 'const CMISSBool DummyInputBool'
            apply_to = 'const CMISSBool *%(name)s' % properties
    if typemap:
        return ('%%apply (%s){(%s)};' % (typemap, apply_to),
            '%%clear (%s);' % apply_to)
    else:
        return '', ''
