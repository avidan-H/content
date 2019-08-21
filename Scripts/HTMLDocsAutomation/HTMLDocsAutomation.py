import demistomock as demisto
from CommonServerPython import *
from CommonServerUserPython import *
import os
import json
import yaml

CMD_ARGS_REGEX = re.compile(r'([\w_-]+)=((?:\"[^"]+\")|(?:`.+`)|(?:\"\"\".+\"\"\")|(?:[^ ]+)) ?', re.S)


"""STRING TEMPLATES"""
OVERVIEW: str = '''
<p>
  Overview description in this section without a header.
</p>
'''

USE_CASES_SINGLE: str = '''
<h2>Use Cases</h2>
<p>Single use case.</p>
'''

USE_CASES_MULTIPLE: str = '''
<h2>Use Cases</h2>
<ul>
  <li>Multiple 1</li>
  <li>Multiple 2</li>
  <li>Multiple 3</li>
</ul>
'''

GENERAL_SECTION: str = '''
<h2>{title}</h2>
<p>
{data}
</p>
'''

DETAILED_DESCRIPTION: str = '''
<h2>Detailed Description</h2>
<p>
{detailed_description}
</p>
'''

FETCH_INCIDENT: str = '''
<h2>Fetch Incidents</h2>
<p>
{fetch_data}
</p>
'''

SETUP_CONFIGURATION: str = '''
<h2>Configure {integration_name} on Demisto</h2>
<ol>
  <li>Navigate to&nbsp;<strong>Settings</strong>&nbsp;&gt;&nbsp;<strong>Integrations</strong>&nbsp;&gt;&nbsp;<strong>Servers &amp; Services</strong>.</li>
  <li>Search for {integration_name}.</li>
  <li>
    Click&nbsp;<strong>Add instance</strong>&nbsp;to create and configure a new integration instance.
    <ul>
      <li><strong>Name</strong>: a textual name for the integration instance.</li>
    </ul>
  </li>
</ol>
<ol start="4">
  <li>
    Click&nbsp;<strong>Test</strong>&nbsp;to validate the new instance.
  </li>
</ol>
'''

COMMANDS_HEADER: str = '''
<h2>Commands</h2>
<p>
  You can execute these commands from the Demisto CLI, as part of an automation, or in a playbook. 
  After you successfully execute a command, a DBot message appears in the War Room with the command details.
</p>
<ol>
  {command_list}
</ol>
'''

COMMAND_LIST: str = '''
<li>{command_hr}: {command}</li>
'''

SINGLE_COMMAND: str = '''
<h3>{index}. {command_hr}</h3>
<hr>
<p>{command_description}</p>
<h5>Base Command</h5>
<p>
  <code>{command}</code>
</p>
<h5>Required Permissions</h5>
<p>The following permissions are required for all commands.</p>
<ul>
    <li>permission 1</li>
    <li>permission 2</li>
</ul>
<h5>Input</h5>
{arg_table}
<p>&nbsp;</p>
<h5>Context Output</h5>
{context_table}
<p>&nbsp;</p>
<h5>Command Example</h5>
<p>
  <code>{command_example}</code>
</p>
<h5>Context Example</h5>
<pre>
  {context_example}
</pre>
<h5>Human Readable Output</h5>
<p>
  {hr_example}
</p>
'''

ARG_TABLE: str = '''
<table style="width:750px" border="2" cellpadding="6">
  <thead>
    <tr>
      <th>
        <strong>Argument Name</strong>
      </th>
      <th>
        <strong>Description</strong>
      </th>
      <th>
        <strong>Required</strong>
      </th>
    </tr>
  </thead>
  <tbody>
{arg_records}
  </tbody>
</table>
'''

ARG_RECORD: str = '''
    <tr>
      <td>{arg_name}</td>
      <td>{arg_description}</td>
      <td>{arg_required}</td>
    </tr>
'''

CONTEXT_TABLE: str = '''
<table style="width:750px" border="2" cellpadding="6">
  <thead>
    <tr>
      <th>
        <strong>Path</strong>
      </th>
      <th>
        <strong>Type</strong>
      </th>
      <th>
        <strong>Description</strong>
      </th>
    </tr>
  </thead>
  <tbody>
    {context_records}
  </tbody>
</table>
'''

CONTEXT_RECORD: str = '''
  <tr>
    <td>{path}</td>
    <td>{type}</td>
    <td>{description}</td>
  </tr>
'''


def get_yaml_obj(entry_id):
    data = {}  # type: dict
    try:
        yml_file_path = demisto.getFilePath(entry_id)['path']
        with open(yml_file_path, 'r') as yml_file:
            data = yaml.safe_load(yml_file)
        if not isinstance(data, dict):
            raise ValueError()

    except (ValueError, yaml.YAMLError):
        return_error('Failed to open integration file')

    return data


def get_command_examples(entry_id):
    """
    get command examples from command file

    @param entry_id: an entry ID of a command file or the content of such file

    @return: a list of command examples
    """
    commands = []  # type: list
    errors = []  # type: list
    if entry_id is None:
        return commands, errors

    if re.match(r'[\d]+@[\d\w-]+', entry_id) is not None:
        examples_path = demisto.getFilePath(entry_id)['path']
        with open(examples_path, 'r') as examples_file:
            commands = examples_file.read().split('\n')
    else:
        demisto.debug('failed to open command file, tried parsing as free text')
        commands = entry_id.split('\n')

    demisto.debug('found the following commands:\n{}'.format('\n* '.join(commands)))
    return commands, errors


def build_example_dict(command_examples):
    """
    gets an array of command examples, run them one by one and return a map of
        {base command -> (example command, markdown, outputs)}
    Note: if a command appears more then once, run all occurrences but stores only the first.
    """
    examples = {}  # type: dict
    errors = []  # type: list
    for example in command_examples:
        if example.startswith('!'):
            cmd, md_example, context_example, cmd_errors = run_command(example[1:])
            errors.extend(cmd_errors)

            if cmd not in examples:
                examples[cmd] = (example, md_example, context_example)

    return examples, errors


def extract_command(cmd_example):
    cmd = cmd_example
    args = dict()  # type: dict
    if ' ' in cmd_example:
        cmd, args_str = cmd_example.split(' ', 1)
        args = dict([(k, v.strip('"`')) for k, v in CMD_ARGS_REGEX.findall(args_str)])

    return cmd, args


def run_command(command_example):
    errors = []
    context_example = ''
    md_example = ''
    cmd = command_example
    try:
        cmd, kwargs = extract_command(command_example)
        res = demisto.executeCommand(cmd, kwargs)

        for entry in res:
            if is_error(entry):
                demisto.results(res)
                raise RuntimeError('something went wrong with your command: {}'.format(command_example))

            raw_context = entry.get('EntryContext', {})
            if raw_context is not None:
                context = {k.split('(')[0]: v for k, v in raw_context.items()}
                context_example += json.dumps(context, indent=4)
            if entry.get('HumanReadable') is None:
                if entry.get('Contents') is not None:
                    content = entry.get('Contents')
                    if isinstance(content, STRING_TYPES):
                        md_example += content
                    else:
                        md_example += json.dumps(content)
            else:
                md_example += entry.get('HumanReadable')

    except RuntimeError:
        errors.append('The provided example for cmd {} has failed...'.format(cmd))

    except Exception as e:
        errors.append(
            'Error encountered in the processing of command {}, error was: {}. '.format(cmd, str(e))
            + '. Please check your command inputs and outputs')

    return cmd, md_example, context_example, errors


def add_lines(line):
    output = re.findall(r'^\d+\..+', line, re.MULTILINE)
    return output if output else [line]


def to_html_table(object=None, headers=None, data=None):
    pass


def human_readable_example_to_html(hr_sample):
    table_regex = re.compile(r'(\|(.*\|)+\s\|(?:---\|)+\s(\|(?:.*\|)+\s?)+)')
    hr_html = []
    while hr_sample:
        truncate = 0
        if hr_sample.startswith('#'):
            title = hr_sample.split('\n', 1)[0]

            while title[truncate:].startswith('#'):
                truncate += 1

            hr_html.append('<h{0}>{1}</h{0}>'.format(truncate, title[truncate + 1:]))
            truncate = len(hr_sample.split('\n', 1)[0])

        table = table_regex.match(hr_sample)
        if table:
            headers = table.group(2)
            data = map(lambda l: l.split('|')[1:-1], table.group(3).split('\n'))
            hr_html.append(to_html_table(headers=headers, data=data))
            truncate = len(table.group(0))

        hr_sample = hr_sample[truncate:]


def addErrorLines(scriptToScan, scriptType):
    res = ''
    if 'python' in scriptType:
        errorKeys = ['return_error', 'raise ']
    elif 'javascript' in scriptType:
        errorKeys = ['throw ']
    # Unsupported script type
    else:
        return res
    linesToSkip = 0
    scriptLines = scriptToScan.splitlines()
    for idx in range(len(scriptLines)):
        # Skip lines that were already scanned
        if linesToSkip > 0:
            linesToSkip -= 1
            continue
        line = scriptLines[idx]
        if any(key in line for key in errorKeys):
            if '(' in line:
                bracketOpenIdx = line.index('(') + 1
                if ')' in line:
                    bracketCloseIdx = line.index(')')
                    res += '* ' + line[bracketOpenIdx:bracketCloseIdx] + '\n'
                # Handle multi line error
                else:
                    res += '*' + ('' if len(line[bracketOpenIdx:].lstrip()) < 1 else ' ' + line[bracketOpenIdx:] + '\n')
                    while ')' not in scriptLines[idx + linesToSkip + 1]:
                        linesToSkip += 1
                        line = scriptLines[idx + linesToSkip]
                        res += ' ' + line.lstrip() + '\n'
                    # Adding last line of error
                    linesToSkip += 1
                    line = scriptLines[idx + linesToSkip]
                    bracketCloseIdx = line.index(')')
                    res += line[:bracketCloseIdx].lstrip() + '\n'
            else:
                firstMatchingErrorKey = next((key for key in errorKeys if key in line), False)
                afterErrorKeyIdx = line.index(firstMatchingErrorKey) + len(firstMatchingErrorKey)  # type: ignore
                res += '* ' + line[afterErrorKeyIdx:] + '\n'
    return res


def generate_use_case_section(title, data):
    html_section = [
        '<h2>{}</h2>'.format(title),
    ]

    if not data:
        data = ''

    if os.linesep in data:
        html_section.append('<ul>')
        html_section.extend('<li>{}</li>'.format(s) for s in data.split(os.linesep))
        html_section.append('</ul>')
    else:
        html_section.append('<p>{}</p>'.format(data))

    return html_section


def generate_section(title, data):
    html_section = [
        '<h2>{}</h2>'.format(title),
    ]

    if data:
        if os.linesep in data:
            html_section.append('<ul>')
            html_section.extend('<li>{}</li>'.format(s) for s in data.split(os.linesep))
            html_section.append('</ul>')
        else:
            html_section.append('<p>{}</p>'.format(data))

    return os.linesep.join(html_section)


# Setup integration on Demisto
def generate_setup_section(yaml_data):
    section = [
        '1. Navigate to __Settings__ > __Integrations__ > __Servers & Services__.',
        '2. Search for {}.'.format(yaml_data['name']),
        '3. Click __Add instance__ to create and configure a new integration instance.',
        '    * __Name__: a textual name for the integration instance.',
    ]
    for conf in yaml_data['configuration']:
        if conf['display']:
            section.append('    * __{}__'.format(conf['display']))
        else:
            section.append('    * __{}__'.format(conf['name']))
    section.append('4. Click __Test__ to validate the URLs, token, and connection.')

    return section


# Commands
def generate_commands_section(yaml_data, example_dict):
    errors: list = []
    command_sections: list = []

    commands = yaml_data['script']['commands']
    command_list = [COMMAND_LIST.format(command_hr=cmd['name'], command=cmd['name']) for cmd in commands]

    for i, cmd in enumerate(commands):
        cmd_section, cmd_errors = generate_single_command_section(i, cmd, example_dict)
        command_sections.extend(cmd_section)
        errors.extend(cmd_errors)

    return (COMMANDS_HEADER.format(command_list=''.join(command_list) + '\n'.join(command_sections))), errors


def generate_single_command_section(index, cmd, example_dict):
    cmd_example: str = example_dict.get(cmd['name'], '')
    errors: list = []
    template: dict = {
        'index': index,
        'command_hr': cmd['name'],
        'command': cmd['name'],
        'command_description': cmd.get('description', ' '),
    }

    # Inputs
    arguments: list = cmd.get('arguments')
    if arguments is None:
        template['arg_table'] = 'There are no input arguments for this command.'
    else:
        arg_table: list = []
        for arg in arguments:
            if not arg.get('description'):
                errors.append(
                    'Error! You are missing description in input {} of command {}'.format(arg['name'], cmd['name']))
            required_status = 'Required' if arg.get('required') else 'Optional'
            arg_table.append(ARG_RECORD.format(name=arg['name'],
                                               description=arg.get('description'),
                                               required=required_status))
        template['arg_table'] = ARG_TABLE.format(records='\n'.join(arg_table))

    # Context output
    outputs: list = cmd.get('outputs')
    if outputs is None:
        template['context_table'] = 'There is no context output for this command.'
    else:
        context_table: list = []
        for output in outputs:
            if not output.get('description'):
                errors.append(
                    'Error! You are missing description in output {} of command {}'.format(output['contextPath'],
                                                                                           cmd['name']))
            context_table.append(CONTEXT_RECORD.format(path=output['contextPath'],
                                                       type=output.get('type', 'unknown'),
                                                       description=output.get('description').encode('utf-8')))
        template['context_table'] = CONTEXT_TABLE.format(records='\n'.join(context_table))

    # Raw output:
    example_template, example_errors = generate_command_example(cmd, cmd_example)
    template.update(example_template)
    errors.extend(example_errors)

    return SINGLE_COMMAND.format(**template), errors


def generate_command_example(cmd, cmd_example=None):
    errors: list = []
    context_example = None
    md_example: str = ''
    if cmd_example is not None:
        cmd_example, md_example, context_example = cmd_example
    else:
        cmd_example = ' '
        errors.append('did not get any example for {}. please add it manually.'.format(cmd['name']))

    example = {
        'command_example': cmd_example,
        'hr_example': human_readable_example_to_html(md_example)
    }
    if context_example:
        example['context_example'] = context_example

    return example, errors


def generate_html_docs(args, yml_data, example_dict, errors):
    docs: str = ''
    # Overview
    overview = (args.get('overview', yml_data.get('description'))
                + '\n\nThis integration was integrated and tested with version xx of {}'.format(yml_data['name']))
    docs += OVERVIEW.format(overview=overview)

    # Playbooks
    docs += generate_section('{} Playbook'.format(yml_data['name']),
                             'Populate this section with relevant playbook names.'),

    # Use Cases
    docs += generate_section('Use Cases',
                             args.get('useCases', 'Use case 1\nUse case 2'))

    # Detailed Descriptions
    docs += generate_section('Detailed Description',
                             yml_data.get('detaileddescription',
                                          'Populate this section with the .md file contents for detailed description.'))
    # Fetch Data
    docs += generate_section('Fetch Incidents',
                             args.get('fetchedData',
                                      'Populate this section with Fetch incidents data'))

    # Setup Configuration
    docs += SETUP_CONFIGURATION.format(integration_name=yml_data['name'])
    # # Setup integration to work with Demisto
    #
    # docs.extend(generate_section('Configure {} on Demisto'.format(yml_data['name']), args.get('setupOnIntegration')))
    # # Setup integration on Demisto
    # docs.extend(generate_setup_section(yml_data))

    # Commands
    command_section, command_errors = generate_commands_section(yml_data, example_dict)
    docs += command_section
    errors.extend(command_errors)

    # Additional info
    docs += generate_section('Additional Information', args.get('addInfo'))

    # Known limitations
    docs += generate_section('Known Limitations', args.get('limit'))

    # Troubleshooting
    docs += generate_section('Troubleshooting', args.get('troubleshooting'))

    # Possible Errors
    if args.get('withErrors') == 'True':
        docs += generate_section('Possible Errors (DO NOT PUBLISH ON ZENDESK):',
                                 addErrorLines(yml_data['script']['script'], yml_data['script']['type']))

    return docs


def main():
    args: dict = demisto.args()
    yml_data: dict = get_yaml_obj(args['entryID'])
    command_examples, errors = get_command_examples(args.get('commands'))
    example_dict, build_errors = build_example_dict(command_examples)
    errors.extend(build_errors)

    docs: str = generate_html_docs(args, yml_data, example_dict, errors)

    filename = '{}-documentation.txt'.format(yml_data['name'])

    demisto.results({
        'Type': entryTypes['note'],
        'ContentsFormat': formats['html'],
        'Contents': docs,
        # 'HumanReadable': docs,
    })
    demisto.results(fileResult(filename, docs, file_type=entryTypes['entryInfoFile']))
    if len(errors) != 0:
        errors.append('Visit the documentation page for more details: '
                      'https://github.com/demisto/content/tree/master/docs/integration_documentation')
        return_error('\n'.join('* {}'.format(e) for e in errors))


if __name__ == '__builtin__':
    main()
