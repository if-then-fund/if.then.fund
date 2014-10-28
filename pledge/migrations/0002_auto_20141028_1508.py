# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pledge', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='trigger',
            name='total_contributions',
            field=models.DecimalField(help_text='A cached total amount of campaign contributions executed (including pending contributions, but not vacated or aborted contributions).', decimal_places=2, default=0, max_digits=6),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='trigger',
            name='total_pledged',
            field=models.DecimalField(help_text='A cached total amount of pledges, i.e. prior to execution.', decimal_places=2, default=0, max_digits=6),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='contribution',
            name='amount',
            field=models.DecimalField(help_text='The amount of the contribution, in dollars.', decimal_places=2, max_digits=6),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='pledge',
            name='amount',
            field=models.DecimalField(help_text='The pledge amount in dollars, not including fees.', decimal_places=2, max_digits=6),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='pledgeexecution',
            name='charged',
            field=models.DecimalField(help_text="The amount the user's account was actually charged, in dollars. It may differ from the pledge amount to ensure that contributions of whole-cent amounts could be made to candidates, and it will include fees.", decimal_places=2, max_digits=6),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='pledgeexecution',
            name='contributions_executed',
            field=models.DecimalField(help_text='The total amount of executed camapaign contributions to-date.', decimal_places=2, max_digits=6),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='pledgeexecution',
            name='contributions_pending',
            field=models.DecimalField(help_text='The current total amount of pending camapaign contributions.', decimal_places=2, max_digits=6),
            preserve_default=True,
        ),
    ]
