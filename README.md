# NFe XML Import for Stock and Inventory

Import Brazilian **NFe XML** files directly into Odoo with automatic **stock** and **inventory** updates.

This module streamlines the goods receipt process by reading official NFe XML files and turning them into accurate inventory operations inside Odoo.

---

## 🚀 Key Features

* Automatic import of Brazilian NFe XML files into Inventory
* Real-time stock level updates after processing
* Automatic creation of **Products** and **Partners** if they do not exist
* Processed NFe history to prevent duplicate imports
* Fully integrated with **Inventory (Stock)** and **Purchases**
* Designed for high-volume XML processing with reliability

---

## 🧩 Integration

This module integrates seamlessly with:

* Inventory
* Products
* Accounting
* Purchase flow

---

## ⚙️ Technical Details

| Item                       | Description           |
| -------------------------- | --------------------- |
| Odoo Version               | 18.0                  |
| License                    | OPL-1                 |
| External Python Dependency | `lxml`                |
| Category                   | Inventory / Inventory |

---

## 📦 Dependencies

The following Odoo modules must be installed:

* `base`
* `stock`
* `product`
* `account`

---

## 🖼️ Screenshots

![Main Screenshot](/nfe_xml_import/static/description/main_screenshot.png)

---

## 🛠️ How It Works

1. Upload an NFe XML file
2. The system reads supplier, products, quantities, and values
3. Missing products or partners are automatically created
4. A stock operation is generated and validated
5. Inventory levels are updated instantly
6. The NFe is logged to prevent reprocessing

---

## ✅ Benefits

* Eliminates manual product entry
* Prevents stock inconsistencies
* Speeds up goods receipt process
* Reduces human errors
* Ensures traceability of all imported NFes

---

## 👨‍💻 Author

**PineappleTech**
https://pineappletec.com.br

---

## 📄 License

OPL-1

---

## 💬 Support

For support or customizations, please contact the author.
