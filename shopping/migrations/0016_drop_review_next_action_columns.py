from django.db import migrations


def drop_next_action_columns(apps, schema_editor):
    table_names = [
        "shopping_storeplanninggooglemapsreviewanalysis",
        "shopping_storeplanninggooglemapsplacesummary",
    ]
    existing_tables = schema_editor.connection.introspection.table_names()
    with schema_editor.connection.cursor() as cursor:
        for table_name in table_names:
            if table_name not in existing_tables:
                continue
            columns = [
                column.name
                for column in schema_editor.connection.introspection.get_table_description(
                    cursor, table_name
                )
            ]
            if "next_action" not in columns:
                continue
            quoted_table_name = schema_editor.quote_name(table_name)
            quoted_column_name = schema_editor.quote_name("next_action")
            cursor.execute(
                f"ALTER TABLE {quoted_table_name} DROP COLUMN {quoted_column_name}"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("shopping", "0015_storeplanninggooglemapsplacesummary"),
    ]

    operations = [
        migrations.RunPython(drop_next_action_columns, migrations.RunPython.noop),
    ]
