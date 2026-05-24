# Azure Order-to-Cash Analytics Platform

An end-to-end data engineering and analytics solution that converts operational business transactions into financial and operational decision intelligence.

This project models a real company Order-to-Cash (O2C) lifecycle and demonstrates how raw operational records become CFO-level reporting.

---

## Business Problem

Companies collect transactional data from multiple operational systems:
- Orders system
- Shipping system
- Billing system
- Payments system

The problem:
Data exists but leadership cannot answer critical questions:

• Why is cash collection delayed?  
• Which customers create revenue vs risk?  
• Which shipments impact invoice cycle time?  
• Where is revenue leakage occurring?

This project builds a full analytics platform to solve that.

---

## End-to-End Workflow

Raw Transactions → Data Lake → ETL Processing → SQL Warehouse → Data Model → BI Dashboard → Business Decisions

---

## Solution Architecture

Operational CSV data is ingested into a cloud storage layer, validated and transformed through a Python ETL pipeline, structured into a dimensional warehouse model, and exposed to Power BI for analytics.

---

## Data Engineering Pipeline

### 1. Raw Data Layer (Azure Blob Storage)
Contains unprocessed operational records:
- customers
- orders
- shipments
- invoices
- payments

This simulates ERP system exports.

### 2. ETL Processing (Python)
Script: `etl/otc_etl_with_validation.py`

ETL performs:
- schema validation
- null handling
- date standardization
- duplicate removal
- business rule validation
- referential integrity checks

### 3. Data Warehouse (SQL)

Structured relational warehouse built using fact and dimension design.

**Fact Tables**
- FactOrders
- FactInvoices
- FactPayments
- FactShipments

**Dimension Tables**
- DimCustomer
- DimDate
- DimProduct

Star schema enables BI performance and business readability.

### 4. Semantic Layer (SQL Views)
Business-friendly views created:
- revenue view
- collection aging
- customer performance
- shipment delay metrics

### 5. Analytics Layer (Power BI)
Power BI connects to warehouse and produces KPI reporting dashboards.

---

## Key Business KPIs Delivered

Financial Performance
- Total Revenue
- Monthly Revenue Trend
- Outstanding Receivables

Operational Efficiency
- Order Fulfillment Cycle Time
- Shipment Delay Rate
- Invoice Generation Lag

Credit & Collections
- Average Payment Delay
- High-Risk Customers
- Collection Efficiency

Customer Intelligence
- Top Revenue Customers
- Low Margin Customers
- Payment Behavior Segmentation

---

## Repository Structure
Data_samples/ → Raw operational data
etl/ → Python ETL pipeline
Docs/ → Case study explanation
Screenshots/ → Proof of pipeline execution
PowerBI Dashboard/ → Final BI output
requirements.txt → Project dependencies


---

## Technology Stack

| Layer | Technology |
|------|------|
| Storage | Azure Blob Storage |
| Processing | Python |
| Data Warehouse | SQL |
| Data Modeling | Star Schema |
| Analytics | Power BI |
| Transformation | ETL Validation Logic |

---

## What This Project Demonstrates

• Realistic business analytics workflow  
• Data engineering fundamentals  
• Data quality validation  
• Dimensional modeling  
• SQL analytics design  
• Business KPI reporting  
• Converting raw data into decision intelligence

---

## Screenshots

Refer `/Screenshots` folder for:
- data ingestion
- ETL execution
- table loading
- schema model
- Power BI dashboard

---

## Pipeline Execution Proof

### Data Lake Storage
![Blob](Screenshots/02_blob_storage_raw_files.png)

### ETL Execution
![ETL](Screenshots/03_etl_pipeline_execution.png)

### SQL Tables Loaded
![SQL](Screenshots/05_sql_tables_loaded.png)

### Star Schema Model
![Model](Screenshots/08_powerbi_data_model.png)


## Power BI Dashboard Preview

### Executive Overview
![Dashboard](Screenshots/10_powerbi_dashboard.png)

The dashboard provides management visibility into revenue realization, customer payment behavior, and operational efficiency across the Order-to-Cash cycle.

Users can:
- monitor monthly revenue performance
- identify delayed payments
- track shipment efficiency
- analyze customer contribution


## Outcome

This project replicates how an organization builds an internal analytics platform to track revenue realization, operational efficiency, and customer payment behavior from operational transaction data.

---

