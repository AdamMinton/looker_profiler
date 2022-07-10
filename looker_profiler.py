import looker_sdk
from looker_sdk import models
import argparse
from pathlib import Path
import json
import progressbar


def profile_query(sdk, model_name, explore_name, dimension, dimension_type, profile_measure):
    limit = '500'

    if dimension_type == 'number':
        filter = 'NOT NULL'
    elif dimension_type == 'string':
        filter = '-EMPTY'
    elif dimension_type == 'date_date':
        filter = '-NULL'
    elif dimension_type == 'date_month':
        filter = '-NULL'
    elif dimension_type == 'date_quarter':
        filter = '-NULL'
    elif dimension_type == 'date_time':
        filter = '-NULL'
    elif dimension_type == 'date_week':
        filter = '-NULL'
    elif dimension_type == 'date_year':
        filter = '-NULL'
    else:
        filter = ''

    if filter == None:
        filter_string = {}
    else:
        filter_string = {f'{dimension}': f'{filter}'}

    return sdk.create_query(
        body=models.WriteQuery(
            model=model_name,
            view=explore_name,
            fields=[dimension, profile_measure],
            fill_fields=[],
            filters=filter_string,
            sorts=[profile_measure + " desc"],
            limit=limit,
        ))


def create_csv_results(target_file):
    csv_header_line = "model_name" + "," + "explore_name" + "," \
        + "dimension_name" + "," + "dimension_type" + "," \
        + "query_error" + "," + "unique_results"
    with open(target_file, 'w+') as file:
        file.write(csv_header_line)
        file.write('\n')


def write_csv_result(
    target_file, model_name, explore_name, dimension_name, dimension_type,
    query_error, unique_results
):
    csv_line = model_name + "," + explore_name + "," \
        + dimension_name + "," + dimension_type + "," \
        + query_error + "," + str(unique_results)

    with open(target_file, 'a') as file:
        file.write(csv_line)
        file.write('\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ini", default="looker.ini",
                        help="ini file to parse for credentials", required=True)
    parser.add_argument("--section", default="looker",
                        help="section for credentials", required=True)
    parser.add_argument("--model", help="LookML Model", required=True)
    parser.add_argument("--explore", nargs='+', default=[],
                        help="LookML Model", required=False)
    parser.add_argument(
        "--profile_measure", help="LookML releative field name for measure (i.e. count)", required=True)
    parser.add_argument("--file_name", default="profile_results",
                        help="LookML Model", required=False)

    args = parser.parse_args()
    model_name = args.model
    explore_list = args.explore
    profile_measure = args.profile_measure
    file_name = args.file_name + '.csv'
    target_directory = Path(__file__).parent
    target_file = Path.joinpath(target_directory, file_name)

    create_csv_results(target_file=target_file)

    sdk = looker_sdk.init40(config_file=args.ini, section=args.section)

    lookml_model = sdk.lookml_model(lookml_model_name=model_name)

    lookml_model_explore_names = [explore['name']
                                  for explore in lookml_model.explores if 'name' in explore]
    profile_explore_names = [
        x for x in explore_list if x in lookml_model_explore_names]

    for explore_name in profile_explore_names:
        query_error = None
        database_error = None
        lookml_model_explore = sdk.lookml_model_explore(
            lookml_model_name=model_name, explore_name=explore_name)
        profile_dimensions = [dimension
                              for dimension in lookml_model_explore.fields.dimensions if dimension.hidden == False]
        widgets = [
            explore_name + ': ',
            progressbar.Bar(),
            ' ',
            progressbar.Counter(format='%(value)02d/%(max_value)d'),
            ' ',
            progressbar.ETA()
        ]
        pbar = progressbar.ProgressBar(widgets=widgets)
        for profile_dimension in pbar(profile_dimensions):
            try:
                profile_query_return = profile_query(
                    sdk=sdk,
                    model_name=model_name,
                    explore_name=explore_name,
                    dimension=profile_dimension.name,
                    dimension_type=profile_dimension.type,
                    profile_measure=explore_name + '.' + profile_measure
                )
            except:
                query_error = "Unable to write query"
                write_csv_result(
                    target_file, model_name, explore_name,
                    profile_dimension.name, profile_dimension.type,
                    query_error, '')
                continue

            try:
                profile_result = sdk.run_query(query_id=profile_query_return.id,
                                               result_format='json')
            except:
                query_error = "Unable to run query"
                write_csv_result(
                    target_file, model_name, explore_name,
                    profile_dimension.name, profile_dimension.type,
                    query_error, '')
                continue

            database_error = profile_result.find("looker_error")
            if database_error > 0:
                query_error = "Database SQL error"
                write_csv_result(
                    target_file, model_name, explore_name,
                    profile_dimension.name, profile_dimension.type,
                    query_error, '')
                continue

            try:
                profile_result_dict = json.loads(profile_result)
                unique_results = len(profile_result_dict)
            except:
                query_error = "JSON Loading Issue"
                write_csv_result(
                    target_file, model_name, explore_name,
                    profile_dimension.name, profile_dimension.type,
                    query_error, '')
                continue

            write_csv_result(
                target_file, model_name, explore_name,
                profile_dimension.name, profile_dimension.type,
                '', unique_results)


main()
