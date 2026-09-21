# happy-deli-pos-system
Web-based POS and inventory management system for Happy’s Deli Junco.

# Happy's Deli Junco — Retail POS & Inventory Optimization System

A web-based Point-of-Sale (POS) and inventory management system being developed for Happy's Deli Junco as part of CSC 400 — Computer Science Project Seminar at Southern Connecticut State University.

## Project Status

🚧 Currently Under Development — Fall 2026

The project is currently in the early development phase. Requirements, designs, and features may be updated throughout development based on client feedback and testing.

## Project Overview

Happy's Deli Junco currently manages many parts of its sales and inventory process manually. With over 2,000 products and approximately 150–200 transactions per day, manually tracking inventory, product prices, sales, and profitability can become difficult.

The goal of this project is to create an affordable and easy-to-use POS system that connects sales, inventory, and business reporting in one application.

The system is primarily designed to run on an Android tablet at the store counter.

## Problem

The store currently lacks a centralized system for:

- Tracking inventory automatically
- Recording sales
- Monitoring product profitability
- Identifying low-stock products
- Managing employee access
- Tracking suppliers
- Generating profit and loss reports

Manual calculations can also slow down transactions and make it difficult to determine whether missing inventory was sold, damaged, lost, or stolen.

## Proposed Solution

The Retail POS & Inventory Optimization System will provide a tablet-friendly web application that allows employees to process transactions while automatically updating inventory.

The store owner will have access to additional management tools for monitoring sales, inventory, profit margins, employees, and suppliers.

## Core Features

### Point-of-Sale
- Barcode scanning
- Product search
- Automatic tax calculation
- Cash and card transaction recording
- Transaction correction/voiding
- Automatic inventory updates after sales

### Inventory Management
- Real-time inventory tracking
- Product creation and editing
- Low-stock alerts
- Manual inventory adjustments
- CSV product import
- Barcode-based product entry

### Reporting & Analytics
- Profit and loss reports
- Sales summaries
- Product performance
- Profit margin tracking
- Dashboard analytics

### User Management
- Admin and Cashier accounts
- Role-based permissions
- Employee account management
- Restricted access to financial and administrative information

### Supplier Management
- Supplier contact information
- Supplier pricing
- Reorder schedules
- Product/supplier relationships

## User Roles

### Admin
The store owner/administrator will have access to management features including:

- Dashboard
- Inventory management
- Profit & loss reports
- Sales analytics
- Employee management
- Supplier management
- System settings

### Cashier
Cashiers will primarily have access to:

- POS checkout
- Product price lookup
- Stock level lookup

Administrative and sensitive financial information will be restricted.

## Technology Stack

### Frontend
- HTML
- CSS
- JavaScript
- Bootstrap 5
- Chart.js

### Backend
- Python
- Flask

### Database
- PostgreSQL
- SQLAlchemy ORM

### Deployment
Planned deployment technologies include:

- Render or Railway
- Fully Kiosk Browser
- Android tablet

> Deployment and hosting choices are subject to change during development.

## System Architecture

The application will follow a web-based architecture:

User → Web Frontend → Flask Backend/API → PostgreSQL Database

The Flask backend will handle authentication, authorization, business logic, input validation, and communication with the database.

## Development Roadmap

### Phase 1 — Foundation (Weeks 1–3)
- Create GitHub repository and project structure
- Finalize project scope and database schema
- Define authentication and permissions
- Develop UI wireframes
- Initialize Flask project
- Test barcode scanner and kiosk compatibility

### Phase 2 — Core Development (Weeks 4–7)
- Build Admin/Cashier authentication
- Implement product data models
- Add barcode and CSV product entry
- Build POS transaction interface
- Connect transactions to inventory

### Phase 3 — Feature Completion (Weeks 8–11)
- Add low-stock alerts
- Build profit & loss reporting
- Add sales analytics
- Implement supplier management
- Add dashboard charts

### Phase 4 — Polish & Delivery (Weeks 12–16)
- Complete UI improvements
- Perform end-to-end testing
- Test role permissions
- Deploy application
- Verify Android kiosk functionality
- Complete documentation
- Conduct final client review

## Future Enhancements

Features that may be implemented after the core system include:

- AI demand forecasting
- Reorder recommendations
- OCR receipt scanning
- Inventory shrinkage/anomaly detection
- Support for additional store locations

## Team

| Team Member | Role |
|-------------|------|
| Ean Watts | Backend & Testing |
| Jeremiah Trail | Frontend & UX/UI |
| Dheylin Antigua | Database & Project Lead |

## Client

**Happy's Deli Junco**

Client Sponsor: Robert Perez  
Role: Owner / Store Administrator

## Course

CSC 400 — Computer Science Project Seminar  
Southern Connecticut State University  
Fall 2026

---

### Current Development Status

This README will be updated throughout development as features are implemented, tested, modified, or removed.
