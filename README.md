# Custom Fees & Payment System Documentation

## Overview

This system implements a comprehensive custom fee calculation and automatic payment detection system for the EMI Collector app. It uses Razorpay for invoice generation and payment processing, with automatic webhook-based payment detection.

## Features

### 1. Custom Fee Configuration
- **Configurable Late Fees**: Set percentage or fixed amount late fees per loan
- **Grace Period**: Define grace days before late fees apply
- **Additional Interest**: Set additional interest rates for overdue amounts
- **Real-time Calculation**: Automatic calculation updates based on time and configuration

### 2. Automatic Payment Detection
- **Razorpay Integration**: Professional invoice generation and payment processing
- **Webhook Processing**: Automatic payment detection via Razorpay webhooks
- **Payment Breakdown**: Smart allocation of payments to fees, interest, and principal
- **Real-time Updates**: Instant loan status updates upon payment

### 3. Time-based Fee Calculation
- **Automatic Updates**: Daily scheduled fee calculations
- **Progressive Fees**: Fees increase based on days overdue
- **Accurate Calculations**: Precise daily interest calculations
- **Historical Tracking**: Complete audit trail of fee calculations

## Technical Implementation

### Database Schema

#### Enhanced Loan Model
```python
class Loan(db.Model):
    # Custom Fee Configuration
    late_fee_type = db.Column(db.String(20), default='percentage')
    late_fee_amount = db.Column(db.Float, default=0.0)
    late_fee_grace_days = db.Column(db.Integer, default=3)
    additional_interest_rate = db.Column(db.Float, default=0.0)
    total_late_fees = db.Column(db.Float, default=0.0)
    last_calculation_date = db.Column(db.DateTime, default=datetime.utcnow)
```

#### New Tables
- **FeeCalculation**: Track all fee calculations over time
- **RazorpayInvoice**: Track Razorpay invoices and their status
- **Enhanced Payment**: Include Razorpay integration and payment breakdown

### Services

#### 1. Fee Calculation Service (`fee_calculation_service.py`)
- **Purpose**: Handle all fee calculations and payment processing
- **Key Functions**:
  - `calculate_fees_for_loan()`: Calculate current fees for a loan
  - `process_payment()`: Process payments and update loan status
  - `update_all_overdue_loans()`: Batch update all overdue loans

#### 2. Razorpay Service (`razorpay_service.py`)
- **Purpose**: Handle Razorpay integration for invoices and payments
- **Key Functions**:
  - `create_invoice_for_loan()`: Create professional invoices
  - `handle_payment_webhook()`: Process payment webhooks
  - `verify_webhook_signature()`: Security verification

#### 3. Fee Scheduler (`fee_scheduler.py`)
- **Purpose**: Automated scheduling of fee calculations
- **Key Functions**:
  - Daily fee calculations at 6 AM
  - Manual calculation triggers
  - Job management and monitoring

### API Endpoints

#### Loan Configuration
```
GET  /api/loans/{loan_id}/config          # Get loan configuration
PUT  /api/loans/{loan_id}/config          # Update loan configuration
POST /api/loans/{loan_id}/calculate       # Trigger calculation
GET  /api/loans/{loan_id}/payment-calculation  # Get current dues
```

#### Invoice Management
```
POST /api/loans/{loan_id}/create-invoice  # Create Razorpay invoice
GET  /api/loans/{loan_id}/invoices        # Get all invoices for loan
GET  /api/loans/{loan_id}/payment-history # Get payment history
```

#### Webhooks
```
POST /webhooks/razorpay                   # Razorpay payment webhooks
POST /webhooks/manual-payment             # Manual payment entry
GET  /webhooks/invoice-status/{id}        # Check invoice status
```

## Setup Instructions

### 1. Install Dependencies
```bash
pip install razorpay python-dateutil apscheduler
```

### 2. Environment Variables
```bash
# Razorpay Configuration
RAZORPAY_KEY_ID=rzp_test_your_key_id
RAZORPAY_KEY_SECRET=your_key_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret

# Encryption
ENCRYPTION_KEY=your_encryption_key
```

### 3. Database Migration
```python
# Run this to create new tables
from app import create_app
from models import db

app = create_app()
with app.app_context():
    db.create_all()
```

### 4. Webhook Configuration
1. Login to Razorpay Dashboard
2. Go to Settings > Webhooks
3. Create webhook with URL: `https://yourdomain.com/webhooks/razorpay`
4. Enable events: `invoice.paid`, `payment.captured`, `invoice.partially_paid`
5. Set webhook secret in environment variables

## Usage Guide

### For Agents

#### 1. Configure Loan Fees
1. Navigate to Client Details
2. Click on any loan item
3. Click "Configure" button
4. Set custom fees:
   - **Late Fee Type**: Percentage or Fixed Amount
   - **Late Fee Amount**: Amount or percentage
   - **Grace Days**: Days before late fee applies
   - **Additional Interest**: Extra interest rate for overdue

#### 2. Generate Payment Invoices
1. From loan item, click "Send Link"
2. System automatically:
   - Calculates current dues (EMI + late fees + interest)
   - Creates professional Razorpay invoice
   - Sends SMS and email to client
   - Provides shareable payment link

#### 3. Monitor Payments
- Payments are automatically detected via webhooks
- Loan status updates in real-time
- Payment history is maintained
- Fee calculations adjust automatically

### For Developers

#### 1. Custom Fee Calculation
```python
from fee_calculation_service import FeeCalculationService

# Calculate fees for a loan
calculation = FeeCalculationService.calculate_fees_for_loan(loan_id)
print(f"Total due: ₹{calculation['total_due']}")
```

#### 2. Create Invoice
```python
from razorpay_service import RazorpayService

service = RazorpayService()
invoice = service.create_and_send_invoice(
    loan_id=loan_id,
    custom_amount=5000,  # Optional
    send_sms=True,
    send_whatsapp=False
)
```

#### 3. Process Manual Payment
```python
# POST to /webhooks/manual-payment
{
    "loan_id": "loan_uuid",
    "amount": 5000.00,
    "payment_method": "cash",
    "notes": "Manual payment entry"
}
```

## Fee Calculation Logic

### 1. Late Fee Calculation
```python
if days_past_grace > 0:
    if loan.late_fee_type == 'percentage':
        late_fee = base_emi * loan.late_fee_amount / 100
    else:
        late_fee = loan.late_fee_amount
```

### 2. Additional Interest
```python
if loan.additional_interest_rate > 0:
    daily_rate = loan.additional_interest_rate / 100 / 365
    additional_interest = outstanding_amount * daily_rate * days_past_grace
```

### 3. Payment Allocation Priority
1. **Accumulated Late Fees** (from previous months)
2. **Current Late Fee** (this month)
3. **Additional Interest** (overdue interest)
4. **EMI Amount** (regular installment)
5. **Principal Reduction** (excess amount)

## Security Features

### 1. Webhook Verification
- All Razorpay webhooks are cryptographically verified
- Invalid signatures are rejected
- Prevents fraudulent payment notifications

### 2. Access Control
- JWT-based authentication
- Agent can only access their assigned clients
- All API endpoints are protected

### 3. Data Validation
- All inputs are validated and sanitized
- Type checking for amounts and rates
- Prevents negative values and invalid configurations

## Monitoring & Logging

### 1. Comprehensive Logging
- All fee calculations are logged
- Payment processing is tracked
- Webhook events are recorded
- Error conditions are captured

### 2. Audit Trail
- FeeCalculation table tracks all calculations
- Payment table records all transactions
- RazorpayInvoice table tracks invoice lifecycle

### 3. Health Checks
```bash
# Check system health
GET /webhooks/health

# Check scheduler status
GET /api/scheduler/status
```

## Troubleshooting

### Common Issues

#### 1. Webhooks Not Working
- Check webhook URL is accessible
- Verify webhook secret matches
- Check Razorpay dashboard for failed deliveries
- Review webhook logs in application

#### 2. Fee Calculations Incorrect
- Check loan configuration settings
- Verify due dates are correct
- Review calculation logs
- Manual recalculation: `POST /api/loans/{id}/calculate`

#### 3. Payments Not Detected
- Check webhook configuration
- Verify Razorpay integration
- Review payment logs
- Manual payment entry option available

### Support Commands

```python
# Manual fee calculation for all loans
from fee_calculation_service import scheduled_fee_calculation
result = scheduled_fee_calculation()

# Check specific loan calculation
from fee_calculation_service import FeeCalculationService
calc = FeeCalculationService.calculate_fees_for_loan('loan_id')

# Verify webhook signature manually
from razorpay_service import RazorpayService
service = RazorpayService()
is_valid = service.verify_webhook_signature(body, signature)
```

## Future Enhancements

### Planned Features
1. **WhatsApp Integration**: Direct WhatsApp payment links
2. **SMS Reminders**: Automated SMS for due payments
3. **Custom Fee Schedules**: Different fees for different client types
4. **Partial Payment Handling**: Better handling of partial payments
5. **Analytics Dashboard**: Fee collection analytics and reporting

### Customization Options
1. **Fee Templates**: Pre-configured fee templates for different loan types
2. **Client-specific Rules**: Different fee structures per client
3. **Time-based Scaling**: Fees that increase over time
4. **Seasonal Adjustments**: Holiday and seasonal fee adjustments

## API Examples

### 1. Get Payment Breakdown
```bash
curl -X POST http://localhost:5000/webhooks/payment-breakdown \
  -H "Content-Type: application/json" \
  -d '{"loan_id": "loan_123", "amount": 5000}'
```

### 2. Create Invoice
```bash
curl -X POST http://localhost:5000/api/loans/loan_123/create-invoice \
  -H "Authorization: Bearer your_jwt_token" \
  -H "Content-Type: application/json" \
  -d '{"amount": 5000, "send_sms": true}'
```

### 3. Update Loan Configuration
```bash
curl -X PUT http://localhost:5000/api/loans/loan_123/config \
  -H "Authorization: Bearer your_jwt_token" \
  -H "Content-Type: application/json" \
  -d '{
    "late_fee_type": "percentage",
    "late_fee_amount": 2.5,
    "late_fee_grace_days": 5,
    "additional_interest_rate": 1.5
  }'
```

# TVS CREDIT HACKATHON

## Features

- **Agent Authentication & Management** - Secure login system for collection agents with JWT token-based authentication
- **Client & Loan Management** - Comprehensive CRUD operations for managing clients and their loan portfolios
- **EMI Collection Orchestration** - Automated EMI collection workflow with smart scheduling and tracking
- **AI-Powered Voice Calls** - Bland AI integration for 2-way conversational collection calls with payment information
- **Razorpay Payment Integration** - Invoice generation, payment link creation, and automated payment detection
- **Dynamic Fee Calculation** - Custom fee structures with late payment penalties and interest calculations
- **Payment Webhook Processing** - Real-time payment status updates and automated reconciliation
- **Comprehensive Logging System** - Multi-level logging with file rotation for monitoring and debugging
- **Fee Scheduling & Automation** - Background scheduler for automatic fee calculations and reminders
- **Mobile Frontend** - Kivy-based mobile interface for agents to manage collections on-the-go
- **Call Logging & Analytics** - Detailed call history tracking with outcome analysis
- **Database Management** - SQLite database with proper relationships and data integrity
- **Security Features** - Password hashing, secure API endpoints, and encrypted sensitive data storage
- **System Health Monitoring** - Built-in health checks and system status monitoring
- **Backup & Recovery** - Database backup functionality with restore capabilities
