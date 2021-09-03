# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.15] - 2021-05-28

### Fixed
- Default placeholder image render
## Added
- New alias image name controller


## [2.2.14] - 2021-02-02

### Fixed
- Skip quantity update if product is with serial number
- Add message in feed for skipped quantity update
- Category not be deleted if mapping exists


## [2.2.13] - 2020-09-25

### Changed
- demo.xml to data.xml
- Datetime format parsing

### Removed
- Feed sequence records from data.xml
- StockMove POS Order operation


## [2.2.12] - 2020-09-11

### Changed
- Stock move location checked with channel location and associated child locations

### Added
- Set need_sync to True, when pricelist_item is updated.


## [2.2.11] - 2020-09-08

### Added
- Unlink product variant mappings when unlinking product template mapping


## [2.2.10] - 2020-09-07

### Fixed
- Instance kanban view with large numbers
-
### Deprecated
- weight_unit in product.variant.feed


## [2.2.9] - 2020-09-01

### Fixed
- Variant feed write


## [2.2.8] - 2020-09-01

### Fixed
- Import Infinity loop when api_imit==1


## [2.2.7] - 2020-07-16

### Fixed
- Mapping button in feed form view


## [2.2.6] - 2020-07-15

### Fixed
- Dashboard name conflict with website
- Contextualized variant feed dictionary with template it


## [2.2.3] - 2020-07-10

### Changed
- Show parent partner record only in tree view
- Count parent partner record only in Customer count


## [2.2.2] - 2020-07-07

### Fixed
- Set invoice as 'paid' where state == 'posted'


## [2.2.1] - 2020-07-03

### Fixed
- Contextualized mapping with product_id


## [2.1.11] - 2020-06-23

### Fixed
- Duplicate order.line.feed when feed is updated.


## [2.1.10] - 2020-06-18

### Fixed
- On variant creation/updation, barcode unique error due to `barcode == ''`


## [2.1.9] - 2020-05-28

### Fixed
- In Instance Dashboard controller, month label obtained from db stripped.

