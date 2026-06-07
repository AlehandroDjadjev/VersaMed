from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_laboratoryresult_laboratoryresultattachment"),
    ]

    operations = [
        migrations.AddField(
            model_name="laboratoryresult",
            name="patient",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.CASCADE,
                related_name="laboratory_results",
                to="core.patientprofile",
            ),
        ),
    ]
