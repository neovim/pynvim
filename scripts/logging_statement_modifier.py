#!/usr/bin/env python

"""\
Logging Statement Modifier - replace logging calls with pass (or vice versa)
Author: David Underhill <dgu@cs.stanford.edu>
Version: 1.00 (06-Feb-2010)

This script parses a Python file and comments out logging statements, replacing
them with a pass statement (or vice versa).  The purpose of commenting out these
statements is to improve performance.  Even if logging is disabled, arguments to
logging method calls must still be evaluated, which can be expensive.

This tool handles most common cases:
  * Log statements may span multiple lines.
  * Custom logging levels may be added (LEVELS, LEVEL_VALUES).
  * Integral logging levels & named logging levels (DEBUG, etc.) are recognized.
  * Logging statements log(), debug(), ..., critical() are all recognized.
  * Statements with unrecognized logging levels will be left as-is.
  * 'logging' is the assumed logging module name (LOGGING_MODULE_NAME).

However, its ability to parse files is limited:
  * It only operates on logging statements in the form logging.log(<level>, ...)
    and logging.<level>(...).
  * The <level> must either be an integral constant or contain one of the names
    from the LEVELS constant below.
  * If a logging statement is made, it is assumed that no other statement is
    made on the same line as logging statement (except for statements made in
    between the open and close parenthesis of the logging call).  For example,
    a semi-colon and then a second statement on the same line as a logging call
    will not be handled properly.
  * Logging methods must be called through SOME module, e.g., logging.log(), not
    just log().
  * For simplicity, undoing the commenting process relies on a comment left by
    the program on the pass statements it adds when commenting out logging
    statements.  (So don't change the comment it outputs by the pass statement).

To run this command on all of the Python files in a particular folder and its
sub-folders at once, try this (replace '/path/to' as appropriate):
    find . -name '*.py' | xargs -i{} /path/to/logging_statement_modifier.py {}
"""

import logging
from optparse import OptionParser
import re
import sys

# logging level names and values
LEVELS = ['DEBUG', 'INFO', 'WARN', 'WARNING', 'ERROR', 'CRITICAL']
LEVEL_VALUES = [logging.DEBUG, logging.INFO, logging.WARN, logging.WARNING, logging.ERROR, logging.CRITICAL]
LEVELS_DICT = dict(zip(LEVELS, LEVEL_VALUES))

# names of methods in the logging module which perform logging
LOGGING_METHODS_OF_INTEREST = ['log', 'debug', 'info', 'warn', 'warning', 'error', 'critical']

# name of the logging module
LOGGING_MODULE_NAME = 'logging'

# this matches logging.<method>([<first_arg>,]
# STR_RE_LOGGING_CALL = r'%s.(\w+)[(](([^,\r\n]+),)?' % LOGGING_MODULE_NAME
STR_RE_LOGGING_CALL = r'\b(' + '|'.join(LOGGING_METHODS_OF_INTEREST) + r')[(](([^,\r\n]+),)?'

# contents of a pass line (not including prefixed whitespace)
PASS_LINE_CONTENTS = 'pass # replaces next logging statement\n'

# Match a logging call (must only be prefixed with whitespace).  Capture groups
# include the whitespace, the logging method called, and the first argument if
# possible
RE_LOGGING_START = re.compile(r'^(\s+)' + STR_RE_LOGGING_CALL)
RE_LOGGING_START_IN_COMMENT = re.compile(r'^(\s+)#' + STR_RE_LOGGING_CALL)

def main(argv=sys.argv[1:]):
    """Parses the command line comments."""
    usage = 'usage: %prog [options] FILE\n\n' + __doc__
    parser = OptionParser(usage)

    # options
    parser.add_option("-f", "--force",
                      action='store_true', default=False,
                      help="make changes even if they cannot undone before saving the new file")
    parser.add_option("-m", "--min_level",
                      default='NONE',
                      help="minimum level of logging statements to modify [default: no minimum]")
    parser.add_option("-M", "--max_level",
                      default='NONE',
                      help="maximum level of logging statements to modify [default: no maximum]")
    parser.add_option("-o", "--output-file",
                      default=None,
                      help="where to output the result [default: overwrite the input file]")
    parser.add_option("-r", "--restore",
                      action='store_true', default=False,
                      help="restore logging statements previously commented out and replaced with pass statements")
    parser.add_option("-v", "--verbose",
                      action='store_true', default=False,
                      help="print informational messages about changes made")

    (options, args) = parser.parse_args(argv)
    if len(args) != 1:
        parser.error("expected 1 argument but got %d arguments: %s" % (len(args), ' '.join(args)))
    input_fn = args[0]
    if not options.output_file:
        options.output_file = input_fn

    # validate min/max level
    LEVEL_CHOICES = LEVELS + ['NONE']
    min_level_value = 0 if options.min_level == 'NONE' else get_level_value(options.min_level)
    if options.min_level is None:
        parser.error("min level must be an integer or one of these values: %s" % ', '.join(LEVEL_CHOICES))
    max_level_value = 9000 if options.max_level == 'NONE' else get_level_value(options.max_level)
    if options.max_level is None:
        parser.error("max level must be an integer or one of these values: %s" % ', '.join(LEVEL_CHOICES))

    if options.verbose:
        logging.getLogger().setLevel(logging.INFO)

    try:
        return modify_logging(input_fn, options.output_file,
                              min_level_value, max_level_value,
                              options.restore, options.force)
    except OSError as e:
        logging.error(str(e))
        return -1

# matches two main groups: 1) leading whitespace and 2) all following text
RE_LINE_SPLITTER_COMMENT = re.compile(r'^(\s*)((.|\n)*)$')
def comment_lines(lines):
    """Comment out the given list of lines and return them.  The hash mark will
    be inserted before the first non-whitespace character on each line."""
    ret = []
    for line in lines:
        ws_prefix, rest, ignore = RE_LINE_SPLITTER_COMMENT.match(line).groups()
        ret.append(ws_prefix + '#' + rest)
    return ''.join(ret)

# matches two main groups: 1) leading whitespace and 2) all following text
RE_LINE_SPLITTER_UNCOMMENT = re.compile(r'^(\s*)#((.|\n)*)$')
def uncomment_lines(lines):
    """Uncomment the given list of lines and return them.  The first hash mark
    following any amount of whitespace will be removed on each line."""
    ret = []
    for line in lines:
        ws_prefix, rest, ignore = RE_LINE_SPLITTER_UNCOMMENT.match(line).groups()
        ret.append(ws_prefix + rest)
    return ''.join(ret)

def first_arg_to_level_name(arg):
    """Decide what level the argument specifies and return it.  The argument
    must contain (case-insensitive) one of the values in LEVELS or be an integer
    constant.  Otherwise None will be returned."""
    try:
        return int(arg)
    except ValueError:
        arg = arg.upper()
        for level in LEVELS:
            if level in arg:
                return level
        return None

def get_level_value(level):
    """Returns the logging value associated with a particular level name.  The
    argument must be present in LEVELS_DICT or be an integer constant.
    Otherwise None will be returned."""
    try:
        # integral constants also work: they are the level value
        return int(level)
    except ValueError:
        try:
            return LEVELS_DICT[level.upper()]
        except KeyError:
            logging.warning("level '%s' cannot be translated to a level value (not present in LEVELS_DICT)" % level)
            return None

def get_logging_level(logging_stmt, commented_out=False):
    """Determines the level of logging in a given logging statement.  The string
    representing this level is returned.  False is returned if the method is
    not a logging statement and thus has no level.  None is returned if a level
    should have been found but wasn't."""
    regexp = RE_LOGGING_START_IN_COMMENT if commented_out else RE_LOGGING_START
    ret = regexp.match(logging_stmt)
    _, method_name, _, first_arg = ret.groups()
    if method_name not in LOGGING_METHODS_OF_INTEREST:
        logging.debug('skipping uninteresting logging call: %s' % method_name)
        return False

    if method_name != 'log':
        return method_name

    # if the method name did not specify the level, we must have a first_arg to extract the level from
    if not first_arg:
        logging.warning("logging.log statement found but we couldn't extract the first argument")
        return None

    # extract the level of logging from the first argument to the log() call
    level = first_arg_to_level_name(first_arg)
    if level is None:
        logging.warning("arg does not contain any known level '%s'\n" % first_arg)
        return None
    return level

def level_is_between(level, min_level_value, max_level_value):
    """Returns True if level is between the specified min or max, inclusive."""
    level_value = get_level_value(level)
    if level_value is None:
        # unknown level value
        return False
    return level_value >= min_level_value and level_value <= max_level_value

def split_call(lines, open_paren_line=0):
    """Returns a 2-tuple where the first element is the list of lines from the
    first open paren in lines to the matching closed paren.  The second element
    is all remaining lines in a list."""
    num_open = 0
    num_closed = 0
    for i, line in enumerate(lines):
        c = line.count('(')
        num_open += c
        if not c and i==open_paren_line:
            raise Exception('Exception open parenthesis in line %d but there is not one there: %s' % (i, str(lines)))
        num_closed += line.count(')')

        if num_open == num_closed:
            return (lines[:i+1], lines[i+1:])

    print(''.join(lines))
    raise Exception('parenthesis are mismatched (%d open, %d closed found)' % (num_open, num_closed))

def modify_logging(input_fn, output_fn, min_level_value, max_level_value, restore, force):
    """Modifies logging statements in the specified file."""
    # read in all the lines
    logging.info('reading in %s' % input_fn)
    fh = open(input_fn, 'r')
    lines = fh.readlines()
    fh.close()
    original_contents = ''.join(lines)

    if restore:
        forwards = restore_logging
        backwards = disable_logging
    else:
        forwards = disable_logging
        backwards = restore_logging

    # apply the requested action
    new_contents = forwards(lines, min_level_value, max_level_value)

    # quietly check to see if we can undo what we just did (if not, the text
    # contains something we cannot translate [bug or limitation with this code])
    logging.disable(logging.CRITICAL)
    new_contents_undone = backwards(new_contents.splitlines(True), min_level_value, max_level_value)
    logging.disable(logging.DEBUG)
    if original_contents != new_contents_undone:
        base_str = 'We are unable to revert this action as expected'
        if force:
            logging.warning(base_str + " but -f was specified so we'll do it anyway.")
        else:
            logging.error(base_str + ', so we will not do it in the first place.  Pass -f to override this and make the change anyway.')
            return -1

    logging.info('writing the new contents to %s' % output_fn)
    fh = open(output_fn, 'w')
    fh.write(new_contents)
    fh.close()
    logging.info('done!')
    return 0

def check_level(logging_stmt, logging_stmt_is_commented_out, min_level_value, max_level_value):
    """Extracts the level of the logging statement and returns True if the
    level falls betwen min and max_level_value.  If the level cannot be
    extracted, then a warning is logged."""
    level = get_logging_level(logging_stmt, logging_stmt_is_commented_out)
    if level is None:
        logging.warning('skipping logging statement because the level could not be extracted: %s' % logging_stmt.strip())
        return False
    elif level is False:
        return False
    elif level_is_between(level, min_level_value, max_level_value):
        return True
    else:
        logging.debug('keep this one as is (not in the specified level range): %s' % logging_stmt.strip())
        return False

def disable_logging(lines, min_level_value, max_level_value):
    """Disables logging statements in these lines whose logging level falls
    between the specified minimum and maximum levels."""
    output = ''
    while lines:
        line = lines[0]
        ret = RE_LOGGING_START.match(line)
        if not ret:
            # no logging statement here, so just leave the line as-is and keep going
            output += line
            lines = lines[1:]
        else:
            # a logging call has started: find all the lines it includes and those it does not
            logging_lines, remaining_lines = split_call(lines)
            lines = remaining_lines
            logging_stmt = ''.join(logging_lines)

            # replace the logging statement if its level falls b/w min and max
            if not check_level(logging_stmt, False, min_level_value, max_level_value):
                output += logging_stmt
            else:
                # comment out this logging statement and replace it with pass
                prefix_ws = ret.group(1)
                pass_stmt = prefix_ws + PASS_LINE_CONTENTS
                commented_out_logging_lines = comment_lines(logging_lines)
                new_lines = pass_stmt + commented_out_logging_lines
                logging.info('replacing:\n%s\nwith this:\n%s' % (logging_stmt.rstrip(), new_lines.rstrip()))
                output += new_lines
    return output

def restore_logging(lines, min_level_value, max_level_value):
    """Re-enables logging statements in these lines whose logging level falls
    between the specified minimum and maximum levels and which were disabled
    by disable_logging() before."""
    output = ''
    while lines:
        line = lines[0]
        if line.lstrip() != PASS_LINE_CONTENTS:
            # not our pass statement here, so just leave the line as-is and keep going
            output += line
            lines = lines[1:]
        else:
            # a logging call will start on the next line: find all the lines it includes and those it does not
            logging_lines, remaining_lines = split_call(lines[1:])
            lines = remaining_lines
            logging_stmt = ''.join(logging_lines)
            original_lines = line + logging_stmt

            # replace the logging statement if its level falls b/w min and max
            if not check_level(logging_stmt, True, min_level_value, max_level_value):
                output += logging_stmt
            else:
                # uncomment_lines of this logging statement and remove the pass line
                uncommented_logging_lines = uncomment_lines(logging_lines)
                logging.info('replacing:\n%s\nwith this:\n%s' % (original_lines.rstrip(), uncommented_logging_lines.rstrip()))
                output += uncommented_logging_lines
    return output

if __name__ == "__main__":
    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.WARN)
    sys.exit(main())
