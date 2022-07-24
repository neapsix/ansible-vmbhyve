#!/usr/bin/python

# Copyright: (c) 2022, Benjamin Spiegel <bspiegel100@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function, with_statement

import re

__metaclass__ = type

DOCUMENTATION = r"""
---
module: vm-bhyve

short_description: Interact with the vm-bhyve utility on FreeBSD.

# If this is part of a collection, you need to use semantic versioning,
# i.e. the version is of the form "2.5.0" and not "2.4".
version_added: "0.0.1"

description: Configure the bhyve hypervisor using vm-bhyve commands.

options:
    switch: 
        description: name of switch to create, edit, or remove in vm-bhyve.
        required: true
        type: str
    state:
        description: whether to create, remove, append to, or remove from switch configuration in vm-bhyve.
            - Use I(present) to create or replace a switch.
            - Use I(absent) to remove a switch.
            - Use I(value_present) to create or add something to a switch.
            - Use I(value_absent) to remove something from a switch.
        required: true
        type: str
    interfaces:
        description: interfaces to attach to the switch.
        required: false
        type: str

extends_documentation_fragment:
    - my_namespace.my_collection.vm-bhyve

author:
    - Ben Spiegel (@neapsix)
"""

EXAMPLES = r"""
# Ensure a switch called public exists and is attached to interface em0 and no other interfaces.
  switch: public
  state: present
  interfaces: em0

# Ensure the switch called public does not exist, destroying it if it does.
  switch: public
  state: absent

# Add interfaces to an existing switch called public, creating the switch if it doesn't exist.
  switch: public
  state: value_present
  interfaces:
    - em1
    - em2

# Remove an interface from an existing switch called public.
  switch: public
  state: value_absent
  interfaces: em1

# Create a switch called public wth interfaces em0 and em1 and update it so that it has interfaces em0 and em3, removing em1.
  switch: public
  state: present
  interfaces:
    - em0
    - em1

  switch: public
  state: present
  interfaces:
    - em0
    - em3
"""

RETURN = r"""
# These are examples of possible return values, and in general should use other names for return values.
original_message:
    description: The original name param that was passed in.
    type: str
    returned: always
    sample: 'hello world'
message:
    description: The output message that the test module generates.
    type: str
    returned: always
    sample: 'goodbye'
"""

# TODO: Get the absolute path to the binary
vm = "vm"

from ansible.module_utils.basic import AnsibleModule


class VmbhyveModule(AnsibleModule):
    def make_commands(self):

        state = self.params["state"]
        interfaces = self.params["interfaces"]

        # fail if adding or removing interfaces but no interfaces specified
        if state in ("value_present", "value_absent") and not interfaces:
            return []

        switch = self.params["switch"]
        todo = []

        if state == "absent":
            # try to destroy the switch (ensure it doesn't exist)
            todo.append([vm, "switch", "destroy", switch])
        else:
            # try to create the switch (ensure it exists)
            todo.append([vm, "switch", "create", switch])

        if interfaces and state == "value_present":
            # try to add the listed interfaces
            for item in interfaces:
                todo.append([vm, "switch", "add", switch, item])
        elif interfaces and state == "value_absent":
            # try to remove the listed interfaces
            for item in interfaces:
                todo.append([vm, "switch", "remove", switch, item])
        elif interfaces and state == "present":
            # see what interfaces the switch already has
            current_interfaces = self.get_switch_interfaces()

            # remove any not specified, and add any not already present
            to_remove = set(current_interfaces).difference(interfaces)
            to_add = set(interfaces).difference(current_interfaces)

            for item in to_remove:
                todo.append([vm, "switch", "remove", switch, item])

            for item in to_add:
                todo.append([vm, "switch", "add", switch, item])

        return todo

    def do_commands(self):
        self.changed = False
        todo = self.make_commands()

        commands = []

        for cmd in todo:
            (rc, out, err) = self.run_command(cmd)

            if rc == 0:
                self.changed = True

            result = dict(
                cmd=cmd,
                rc=rc,
                out=out,
                err=err,
            )

            commands.append(result)

        return commands

    def get_switch_interfaces(self):
        switch = self.params["switch"]

        # from the info command output, get the "phsycial-ports:" line
        cmd = [vm, "switch", "info", switch]

        (_, out, _) = self.run_command(cmd)

        found = ""

        match = re.search(r"(?<=physical-ports: ).*?(?=\n)", out)

        if match:
            found = match.group(0)

        interfaces = []

        # if there are no interfaces, physical-ports '-'. don't return that.
        if found != "-":
            interfaces = found.split()

        return interfaces


def run_module():
    # define available parameters a user can pass to the module
    module_args = dict(
        switch=dict(type="str", required=True),
        state=dict(type="str", required=True),
        interfaces=dict(type="list", required=False),
    )

    # Seed the result
    result = dict(changed=False, commands=[])

    # Set up an instance of the module to run commands.
    module = VmbhyveModule(argument_spec=module_args, supports_check_mode=True)

    # Run the commands and note if anything changed
    result["commands"] = module.do_commands()
    result["changed"] = module.changed

    # If in check mode, return the current state with no changes.
    if module.check_mode:
        module.exit_json(**result)

    # Determine whether the module failed
    if module.params["switch"] == "fail me":
        module.fail_json(msg="You requested this to fail", **result)

    # If it execued successfully, pass the key value results.
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
