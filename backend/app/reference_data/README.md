# Postal reference subset

`postal.json` is derived from [GeoNames postal downloads](https://download.geonames.org/export/zip/)
under [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
Credit: **GeoNames, www.geonames.org**. GB data additionally contains Royal Mail
data, Royal Mail copyright and database right 2022.

Changes: a deterministic, subdivision-distributed subset of up to 256 locality,
state and postal-code rows per country; columns not needed by the generator are
omitted. Obvious organization-only and numeric locality labels are filtered.
Full GB and Canadian postcode files are used, preserving complete postcodes.
The JSON records download URLs, retrieval time and source archive SHA-256 hashes.
The subset is not an exhaustive gazetteer or a statistically representative sample.
Locality names may be postal areas, wards or post-office names rather than cities.

The generator supplies fictional street names and house numbers. Reference rows
do not establish street existence, deliverability, current postal validity or
population coverage. GeoNames distributes the source data without a warranty
of accuracy, timeliness or completeness. Source attribution and version hashes
are retained in generated address metadata and dataset exports.

Maintainers can rebuild explicitly with:

```powershell
.venv\Scripts\python.exe -X utf8 scripts/build_postal_reference.py
```

This download command uses the same upstream postal database as pgeocode.
Runtime generation reads the checked-in subset and makes no network requests;
pgeocode/pandas are not required at runtime.
