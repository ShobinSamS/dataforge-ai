# Country-aware synthetic addresses

Select an **address** field, then choose **Address country**. Select the components
you want, move them up/down, and choose **Single line** or **Separate lines**.
You can edit **Address format** directly for custom separators and labels:

```text
{street}
{city}, {state}
{country} {postal_code}
```

Primary components are `street`, `city`, `state`, `country`, `postal_code`.
`house_number`, `street_name`, `state_code`, `country_code` are also available.
Only simple named placeholders are accepted; expressions and format specifiers
are rejected. The `street` component already includes a generated house number.
Make the region tall enough for the chosen number of lines; font controls still
apply and text is fitted within the selected box.

**Preview address** shows an example; **Another address example** advances its
seed. Changes invalidate the preview. Clear **Exact content** to generate fresh
addresses. Choosing a country or changing the format clears previous exact text.
Existing templates/jobs without an address country retain their legacy placeholder.

## Prompts

With the field type set to address, enter:

> Generate a synthetic Indian address containing street, city, state, country and PIN code. Put each component on a separate line.

Or:

> Generate a US address with street, city, state, ZIP code and country on one line.

Or:

> Generate an address in Germany using format: {street}, {postal_code} {city}, {country}

**Apply rule** handles common requests directly. **Interpret with local Qwen**
uses a schema restricted to address country and component format. A PIN/ZIP/postal
code inside an address request is not interpreted as an identifier pattern.
Qwen never supplies a fixed example as the random generator. If the model cannot
compile a common supported rule, the normal known-rule fallback is identified
in the UI. Unsupported countries/constraints fail rather than silently selecting
another country. Specific city/state filters and translations are not implemented.

## Data and consistency

Supported countries: India, United States, United Kingdom, Canada, Australia,
Germany, France, New Zealand, Spain, Italy, Malaysia and Pakistan.

The app bundles a deterministic subset of up to 256 rows per country from
[GeoNames postal data](https://download.geonames.org/export/zip/), under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Locality, state and
postal code are selected together from one row; leading zeros and complete
UK/Canadian postcodes are retained. A locality may be a postal area, ward or
post-office name rather than a municipality. This subset is not exhaustive or
representative of population/address coverage. GB source data contains Royal Mail
data, Royal Mail copyright and database right 2022.

Street names and house numbers are generated fictional content. Street existence,
deliverability and current postal validity are not verified. Generation makes
no internet requests; no geocoding API key or runtime pandas/pgeocode dependency
is required. The reference file is derived from the same upstream used by
[pgeocode](https://pgeocode.readthedocs.io/).

Every generated address annotation records its components, country, format,
source attribution, reference hash and synthetic/deliverability flags. These
remain in dataset metadata and exports. Same-country repeated address fields
share components for a sample, even when each field uses a different layout.
Seeds reproduce the same results with the same reference version.

Reference provenance and the explicit maintainer refresh command are documented
in [reference_data/README.md](../backend/app/reference_data/README.md).

API: `GET /api/addresses/countries`, `POST /api/addresses/preview` and
`POST /api/assets/generate` with `kind: "address"`. MCP: `list_address_countries`
and `generate_address`; normal template/job tools retain the typed options.
