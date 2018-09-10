import argparse
import re

to_debug = False  # FLAG

# constants
SEP = '//'
FORMAT_ANCHOR = '{}'

EXPLANATION = """
For example:
  log.debug("hey1 " + test + " hey2"); -> log.debug("hey1 {} hey2", test);
  log.debug(test + " hey1 " + "hey2");//(comment); -> log.debug("{} hey1 hey2", test);//(comment); 
It is also able to handle brackets:
  log.debug( "hey1" + (test - 2) + "//hey4 "); -> log.debug("hey1{}//hey4 ", (test - 2))
And multiline logging: 
  log.debug( "hey1" + test + 
    "//hey4 ");' -> log.debug("hey1{}//hey4 ", test);
Skips lines with {} and commented lines """


class CurlyBracketsException(Exception):
    pass


def log(info=None, line=None):
    if to_debug:
        if info and line:
            print(info, line)
        else:
            print


def parse_tokens(tokens, overall_msg, var_list, ind=0):
    """ Parses the character tokens in a message, and replaces occurences of string concatentation with parameterization. Adjacent strings are combined together, and variables are replaced with format anchors.

      Args:
          tokens (string): string of characters in the original message
          overall_msg (list<string>): Forms the parameterized logging message with format anchors
          var_list (list<string>): Variables in the logging message
          ind (int): index of the character token to start parsing form

      Returns:
          list<string>: Forms the parameterized logging message with format anchors
          list<string>: Variables in the logging message
          int: index of semi-colon or end of line

    """
    is_end = ind >= len(tokens) or tokens[ind] == ';'
    if is_end:
        return overall_msg, var_list, ind
    else:
        if tokens[ind] == '"':  # Parse string
            string, next_ind = parse_string(tokens, ind + 1)
            overall_msg.append(''.join(string))
        elif tokens[ind].isalnum() or tokens[ind] == '(':  # Parse variable
            variable, next_ind = parse_var(tokens, ind)
            var_list.append(variable)
            overall_msg.append(FORMAT_ANCHOR)  # Insert format anchor
        else:  # Move to next token
            next_ind = ind + 1
        return parse_tokens(tokens, overall_msg, var_list, next_ind)


def parse_string(tokens, ind):
    """ Retrieves a string from the character tokens, starting from a specified index.
      Args:
          tokens (string): string of characters in the original message
          ind (int): index of the character token to start parsing form

      Returns:
          string: String retrieved from the message, starting from the index
          integer: Next index to continue parsing from
      Raises:
          CurlyBracketException: when consecutive curly brace {} is present in the tokens

    """
    string_overall_msg = []
    while tokens[ind] != '"':
        if tokens[ind:ind + 2] == '{}':  # ignore messages with curly brackets
            log("Exception", "Throw curly brackets exception")
            raise CurlyBracketsException()
        string_overall_msg.append(tokens[ind])
        if tokens[ind] == '\\':  # escape character, consider next character
            string_overall_msg.append(tokens[ind + 1])
            ind += 1
        ind += 1
    return ''.join(string_overall_msg), ind + 1


def parse_var(tokens, ind):
    """ Retrieves a variable from the character tokens, starting from a specified index.
      Args:
          tokens (string): string of characters in the original message
          ind (int): index of the character token to start parsing form

      Returns:
          string: variable retrieved from the message, starting from the index
          integer: next index to continue parsing from

    """
    current_var = []
    bracket_num = 0
    while ind < len(tokens) and (bracket_num > 0 or tokens[ind] == '('
                                 or tokens[ind].isalnum()
                                 ):  # it is still a variable, continue parsing
        current_var.append(tokens[ind])
        if tokens[ind] == '(':
            bracket_num += 1
        elif tokens[ind] == ')':
            bracket_num -= 1
        ind += 1
    return ''.join(current_var), ind + 1


def parse_file(f, k_regex):
    """ Iterates through lines in the file, and convert each line containing the keyword regex into the parameterized form.
      Args:
          f: file object to parse
          k_regex: regex of keyword

      Returns:
          list<string>:  all lines in the file, with those containing the keyword converted to its parameterized form
          list<(int, string)>: tuple of (line_number, converted_content) of lines that are changed in the file

    """
    output = []
    changes = []
    for line_idx, file_line in enumerate(f):
        log("Line", file_line)
        preceding_section, tokens = get_tokens(file_line, k_regex)
        if not (preceding_section and tokens):
            output.append(file_line)
            continue
        try:
            logging_msg, variables, comments = parse_line(tokens)
            converted_line = "{}\"{}\", {});{}\n".format(
                preceding_section, logging_msg, variables, comments)
            log("Final overall_msg", converted_line)
            output.append(converted_line)
            changes.append((line_idx + 1, converted_line))
        except CurlyBracketsException:
            output.append(file_line)
            continue
        log()
    return output, changes


def parse_line(tokens):
    """ Converts the logging statement into the parameterized form. Processes the following lines if the logging spans multiple lines
         Args:
            tokens: list of characters in the 1st line of the logging statement

         Returns:
             string:  logging message with format anchor
             string:  variables delimited by comma
             string:  comments following the logging statement
    """
    str_list, var_list, ind = parse_tokens(tokens, overall_msg=[], var_list=[])
    while ind > len(tokens) - 1:  # logging spans multiple lines
        next_line = next(f)  # continue parsing next line
        tokens = list(next_line.lstrip(' ').lstrip('\t'))
        str_list, var_list, ind = parse_tokens(
            tokens, overall_msg=str_list, var_list=var_list)
    logging_msg = ''.join(str_list)
    variables = ', '.join(var_list)
    comments = ''.join(
        tokens[ind + 1:]
    ) if ind < len(tokens) else ''  # remaining characters are comments
    return logging_msg, variables, comments


def get_tokens(file_line, keyword_regex):
    """ Searches for keyword in line to retrieve tokens containing it
         Args:
            file_line: line in file to search for the keyword
            keyword_regex: regex of keyword to search for

         Returns:
             string:  substring from the start of file_line to the keyword_regex (including the keyword regex itself)
             tokens:  substring from after the keyword_regex to the end of the string
    """
    match_comment = re.search(r'//', file_line)
    match_keyword = re.search(
        r'(?<=\b' + keyword_regex + '\()((?!\{.*\}).)*.*$', file_line)
    is_valid = match_keyword and not (
        match_comment and match_comment.start() < match_keyword.start())
    if is_valid:
        preceding_section = file_line[:match_keyword.start(
        )]  # get section preceding the logging message (inclusive of keyword)
        tokens = match_keyword.group()
        return preceding_section, tokens
    else:
        return None, None


if __name__ == "__main__":
    # raw_args = ['-h']
    parser = argparse.ArgumentParser(
        description=
        'Replace string concatenation with parameterization with slf4j logging',
        epilog=EXPLANATION,
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "-m",
        "--modify",
        help="modify the input file in-place",
        action="store_true")
    parser.add_argument("regex", help="regex of keyword to look out for")
    parser.add_argument("filename", help="name of file to refactor")
    args = parser.parse_args()
    with open(args.filename, 'r') as f:
        converted_output, lines_changed = parse_file(f, args.regex)
    if args.modify:
        with open(args.filename, 'w') as f:
            f.write(''.join(converted_output))
    else:
        change_log = '\n'.join([''.join(str(line)) for line in lines_changed])
        print(change_log)
    print('\n'.join([''.join(str(line)) for line in lines_changed]))
