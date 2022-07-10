import argparse
import lkml
import pandas as pd
import os
from lkml.tree import PairNode, SyntaxToken, BlockNode
from lkml.visitors import BasicTransformer
from dataclasses import replace


class AddFieldHiddenTransformer(BasicTransformer):
    def __init__(self, field_search, overwrite_confirmation=True, overwrite_override=False):
        # Create a properly formatted list from messy user input
        self.field_search = field_search.replace(' ', '').split(',')
        self.overwrite_confirmation = overwrite_confirmation
        self.overwrite_override = overwrite_override
        self.view = ''

    def visit_block(self, node: BlockNode) -> BlockNode:
        # We want to know if any of the search terms are present
        if node.type.value == 'view':
            self.view = node.name.value
        if node.type.value == 'dimension' and self.view + '.' + node.name.value in self.field_search:
            # and any(search_term in node.name.value for search_term in self.field_search):
            # Generate the new hidden parameter to add
            # First, check if there's already a hidden parameter, because the new parameter will be formatted differently
            already_contains_hidden = any(
                item.type.value == 'hidden' for item in node.container.items)
            if already_contains_hidden:  # if the hidden parameter already exists
                # is the first parameter 'group_label'?
                if node.container.items[0].type.value == 'hidden':
                    new_hidden = PairNode(
                        SyntaxToken(value='hidden', prefix='', suffix=''),
                        # Don't include a newline character at the end of it, becuase it already exists
                        SyntaxToken(value='yes', prefix='', suffix='')
                    )
                else:
                    new_hidden = PairNode(
                        SyntaxToken(value='hidden', prefix='', suffix=''),
                        # Newline character needs to be added
                        SyntaxToken(value='yes', prefix='', suffix='\n    ')
                    )
            else:  # If hidden parameter doesn't exist
                new_hidden = PairNode(
                    SyntaxToken(value='hidden', prefix='', suffix=''),
                    # Include the newline character at the end of the PairNode
                    SyntaxToken(value='yes', prefix='', suffix='\n    ')
                )

            if not self.overwrite_override:
                # We want to overwrite the hidden parameter, but should probably check to make sure it's okay first
                if self.overwrite_confirmation and already_contains_hidden:
                    overwrite = input(
                        f'The field {node.name.value} already has a hidden parameter. Do you want to overwrite (Y/N):  ')
                    if overwrite.lower() not in ['n', 'no']:
                        pass
                    else:
                        try:
                            return self._visit_container(node)
                        except:
                            return node

            # If we got here, it means overwrite_confirmation == False or overwrite_override == True

            new_items = list(
                item for item in node.container.items if item.type.value != 'hidden')

            # Now we insert the hidden parameter at the front
            new_items.insert(0, new_hidden)

            # Replacing the original node's items with the new items
            new_container = replace(node.container, items=tuple(new_items))
            new_node = replace(node, container=new_container)

            # rebuild the tree with the new node and continue
            return new_node

        # We didn't match the search terms
        else:
            try:
                return self._visit_container(node)
            # nodes that have ListNodes of type = 'filters' in them seem to be throwing FrozenInstanceError messages,
            # but they still work and labels update if they match.
            except:
                return node
            finally:
                pass


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--project_folder",
                        help="LookML Project Folder", required=True)
    parser.add_argument("--file_name", default="profile_results",
                        help="LookML Profile Results Output", required=False)
    parser.add_argument("--minimum_unique_values", type=int, default=2,
                        help="Minimum unique values to not hide fields", required=False)
    args = parser.parse_args()
    project_folder = args.project_folder
    file_name = args.file_name + '.csv'
    minimum_unique_values = args.minimum_unique_values

    # Obtain profile results to determine which dimensions to hide
    profile_results = pd.read_csv(file_name)
    filtered_profile_results = profile_results.loc[profile_results['unique_results']
                                                   < minimum_unique_values]
    # Create a string list of dimensions to hide
    dimensions_to_hide = filtered_profile_results['dimension_name'].tolist(
    )
    dimensions_to_hide_string = ','.join(dimensions_to_hide)

    for path, subdirs, files in os.walk(project_folder):
        for name in files:
            if name.endswith('.lkml'):
                view_path = os.path.join(path, name)
                view_file = open(view_path, 'r')
                data = view_file.read()
                view_file.close()
                tree = lkml.parse(data)

                new_tree = tree.accept(AddFieldHiddenTransformer(
                    dimensions_to_hide_string, overwrite_confirmation=False))

                with open(view_path, 'w+') as new_view_file:
                    new_view_file.write(str(new_tree))

    print('''
    ######################################################################
    Your project folder is the folder that contains your updated views.
    Please review git changes to ensure accuracy.
    #######################################################################
    ''')


main()
