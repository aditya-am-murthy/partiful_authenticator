import csv
import re
from collections import defaultdict

def normalize_name(name):
    """Normalize name for comparison (lowercase, strip spaces)"""
    return name.strip().lower()

def parse_payments(payments_file):
    """Parse payments from payments.txt and return a dict of name -> amount"""
    payments = {}
    
    with open(payments_file, 'r') as f:
        lines = f.readlines()
    
    # Pattern to match payment amounts
    # Look for patterns like "Name paid you $X.00" or "Name sent you $X.00"
    # Handle tabs, spaces, and BofA prefix, capture names with multiple words
    for line in lines:
        # Strip whitespace including tabs
        line = line.strip()
        if not line:
            continue
            
        # Skip lines that are just separators or headers (like "86753:")
        if line.endswith(':') and 'paid' not in line.lower() and 'sent' not in line.lower():
            continue
        
        # Try "paid you" pattern
        match = re.search(r'([A-Za-z][A-Za-z\s\']+?)\s+paid\s+you\s+\$(\d+\.?\d*)', line, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            amount = float(match.group(2))
            normalized_name = normalize_name(name)
            if normalized_name in payments:
                payments[normalized_name] += amount
            else:
                payments[normalized_name] = amount
            continue
        
        # Try "sent you" pattern (with optional BofA: prefix)
        match = re.search(r'(?:BofA:\s+)?([A-Za-z][A-Za-z\s\']+?)\s+sent\s+you\s+\$(\d+\.?\d*)', line, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            amount = float(match.group(2))
            normalized_name = normalize_name(name)
            if normalized_name in payments:
                payments[normalized_name] += amount
            else:
                payments[normalized_name] = amount
            continue
    
    return payments

def main():
    # Read whitelist
    with open('whitelist.txt', 'r') as f:
        whitelist = {normalize_name(line.strip()) for line in f if line.strip()}
    
    # Read no_pay list (guests who don't have to pay)
    with open('no_pay.txt', 'r') as f:
        no_pay = {normalize_name(line.strip()) for line in f if line.strip()}
    
    # Initialize lists
    blacklist = []
    guest_structure = defaultdict(list)  # main guest normalized -> list of plus ones
    main_guests = {}  # Store all main guests: normalized -> actual name
    all_guests = {}  # Store all guests: normalized -> actual name (for lookup)
    
    # Read CSV and process guests
    with open('ICCHalloweenParty_10-29_guests.csv', 'r') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            name = row['Name'].strip()
            status = row['Status'].strip()
            plus_one_of = row['Is Plus One Of'].strip()
            
            # Only consider guests with status "Going"
            if status != 'Going':
                continue
            
            normalized_name = normalize_name(name)
            all_guests[normalized_name] = name
            
            # Check whitelist
            if normalized_name not in whitelist:
                blacklist.append(name)
            
            # Build guest structure
            if plus_one_of:
                # This is a plus one
                main_guest_normalized = normalize_name(plus_one_of)
                guest_structure[main_guest_normalized].append(name)
            else:
                # This is a main guest
                main_guest_normalized = normalize_name(name)
                main_guests[main_guest_normalized] = name
                # Initialize with empty list if not already present
                if main_guest_normalized not in guest_structure:
                    guest_structure[main_guest_normalized] = []
    
    # Parse payments
    payments = parse_payments('payments.txt')
    
    # Price per guest
    PRICE_PER_GUEST = 5.0
    
    # Track who has been accounted for
    accounted_for = set()
    unpaid = []
    
    # Process each main guest and their plus ones
    for main_guest_normalized, plus_ones in guest_structure.items():
        main_guest_name = main_guests.get(main_guest_normalized, all_guests.get(main_guest_normalized, main_guest_normalized.title()))
        
        # Get payment amount for this main guest - try exact match first
        payment_amount = payments.get(main_guest_normalized, 0.0)
        
        # If no exact match, try to find partial matches (in case of name variations)
        if payment_amount == 0.0:
            for payment_name, amount in payments.items():
                # Check if payment name contains main guest name or vice versa
                # Also check if first word of either name matches
                main_first_word = main_guest_normalized.split()[0] if main_guest_normalized.split() else main_guest_normalized
                payment_first_word = payment_name.split()[0] if payment_name.split() else payment_name
                
                if (main_guest_normalized in payment_name or 
                    payment_name in main_guest_normalized or
                    main_first_word == payment_first_word or
                    main_first_word in payment_name or
                    payment_first_word in main_guest_normalized):
                    payment_amount = amount
                    break
        
        # Calculate how many guests are covered by this payment
        # Each guest (main + plus ones) costs $5
        total_guests = 1 + len(plus_ones)  # 1 for main guest + plus ones
        guests_covered = int(payment_amount / PRICE_PER_GUEST)
        
        # Mark accounted guests
        if guests_covered > 0:
            # Main guest is accounted for
            accounted_for.add(main_guest_normalized)
            
            # Plus ones accounted for (up to the number covered)
            for i in range(min(guests_covered - 1, len(plus_ones))):
                plus_one_name = plus_ones[i]
                accounted_for.add(normalize_name(plus_one_name))
        
        # Add unaccounted guests to unpaid list
        if main_guest_normalized not in accounted_for:
            unpaid.append(main_guest_name)
        
        for plus_one in plus_ones:
            plus_one_normalized = normalize_name(plus_one)
            if plus_one_normalized not in accounted_for:
                unpaid.append(plus_one)
    
    # Double check unpaid list - verify they haven't paid
    definitely_not_paid = []
    
    for unpaid_guest in unpaid:
        unpaid_normalized = normalize_name(unpaid_guest)
        # Check if they have any payment recorded (exact or partial match)
        has_payment = unpaid_normalized in payments
        
        # Also check for partial matches (including first word matches)
        if not has_payment:
            unpaid_first_word = unpaid_normalized.split()[0] if unpaid_normalized.split() else unpaid_normalized
            for payment_name in payments.keys():
                payment_first_word = payment_name.split()[0] if payment_name.split() else payment_name
                
                if (unpaid_normalized in payment_name or 
                    payment_name in unpaid_normalized or
                    unpaid_first_word == payment_first_word or
                    unpaid_first_word in payment_name or
                    payment_first_word in unpaid_normalized):
                    has_payment = True
                    break
        
        if not has_payment:
            # Check if guest is on no_pay list - if so, skip them
            if unpaid_normalized not in no_pay:
                definitely_not_paid.append(unpaid_guest)
    
    # Display results
    print("=" * 60)
    print("AUTHENTICATION RESULTS")
    print("=" * 60)
    
    print("\n📋 BLACKLIST (Not on whitelist):")
    if blacklist:
        for guest in blacklist:
            print(f"  - {guest}")
    else:
        print("  (None)")
    
    print("\n❌ DEFINITELY NOT PAID (Unpaid and no payment record):")
    if definitely_not_paid:
        for guest in definitely_not_paid:
            print(f"  - {guest}")
    else:
        print("  (None)")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()

