# `costs_liq_ld_refined_cats_2011.csv`

Indicative land damage cost per property, by observed land damage category, from
the Canterbury earthquake sequence.

## Source

`T:\Christchurch\TT Projects\52020\WorkingMaterial\ILVR\Dec 2016 ILVR\Dec 2016
Land Liability v1.xlsx`, sheet "Rates Tables", table "Cat 1 to 7 Rates Table
(exc GST)".

A description of the study the rates come from is to be supplied by Virginie
Lacrosse and added here.

## What the numbers are

- **Payments in 2010/2011 New Zealand dollars per observed land damage state.**
  They are not escalated to any later date, so anything read out of this file
  has to be brought forward before it is compared with a present-day value.
- **Excluding GST**, per the source table's own heading.
- The three cost columns are the **15th, 50th and 85th percentiles** of cost for
  a given maximum land damage index value, so the spread within a category is
  carried rather than a single point estimate.

## Columns

| Column | Meaning |
| --- | --- |
| `LD_refined_cats` | Refined land damage category, 1 to 6 |
| `source_band` | The band label the row was read from in the source table |
| `cost_15th_percentile_nzd` | 15th percentile cost, 2010/2011 NZD, excluding GST |
| `cost_50th_percentile_nzd` | 50th percentile cost, 2010/2011 NZD, excluding GST |
| `cost_85th_percentile_nzd` | 85th percentile cost, 2010/2011 NZD, excluding GST |

## How the source bands map onto the categories

The source table is banded rather than given per category, so one row there can
supply more than one category here:

- Band "none or 1" supplies category 1. The "none" case is not represented as a
  category of its own; a property with no land damage takes no cost rather than
  the category 1 row.
- Bands "2 or 2.5" and "3 or 3.5" supply categories 2 and 3. The half categories
  fall in with the whole category below them.
- Band "5 or 6" supplies categories 5 and 6, which is why those two rows carry
  identical costs. They are not independent estimates.

The source table is titled "Cat 1 to 7" but its bands stop at "5 or 6". Nothing
in the source as transcribed covers a category 7, so nothing here does either.
Register task **T-28** covers clarifying whether a category 7 exists and was
simply not carried across.

## Limitations

- **These costs are for flatland only.** They come from Canterbury, where the
  observed damage is flat land liquefaction, and they must not be applied to
  hill land or to landslide damage.
- **Whether the costs include damage to retaining walls, culverts and bridges is
  not known.** Register task **T-27** covers confirming it. Until it closes,
  treat the figures as land damage of unknown scope rather than as land damage
  exclusive of those assets.
- The join from these categories to mapped observations is not implemented. No
  code in the repository reads this file yet.
