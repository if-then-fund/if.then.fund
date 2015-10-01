# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('letters', '0005_auto_20150925_1539'),
    ]

    operations = [
        migrations.AddField(
            model_name='letterscampaign',
            name='topic',
            field=models.CharField(null=True, max_length=64, choices=[('Agriculture', 'Agriculture'), ('Banking / Insurance / Financial Services', 'Banking / Insurance / Financial Services'), ('Budget and Economy', 'Budget and Economy'), ('Business and Commerce', 'Business and Commerce'), ('Communications / Science / Technology', 'Communications / Science / Technology'), ('Congress and Campaign Finance', 'Congress and Campaign Finance'), ('Defense and Military', 'Defense and Military'), ('Education', 'Education'), ('Energy', 'Energy'), ('Environment', 'Environment'), ('Foreign Affairs', 'Foreign Affairs'), ('General / Miscellaneous / Other', 'General / Miscellaneous / Other'), ('Health Care', 'Health Care'), ('Homeland Security', 'Homeland Security'), ('Housing and Urban Development', 'Housing and Urban Development'), ('Immigration', 'Immigration'), ('Judiciary', 'Judiciary'), ('Labor and Employment', 'Labor and Employment'), ('Social Security', 'Social Security'), ('Taxes', 'Taxes'), ('Trade', 'Trade'), ('Transportation', 'Transportation'), ('Veterans Affairs', 'Veterans Affairs')], blank=True),
        ),
    ]
