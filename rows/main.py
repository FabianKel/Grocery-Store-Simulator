import heapq
import random

class Customer:
    def __init__(self, id, customer_type, basket_size, urgency):
        self.id = id
        self.type = customer_type
        self.basket_size = basket_size
        self.urgency = urgency
        self.arrival_time = 0
        self.start_service_time = None
        self.departure_time = None
        self.abandoned = False
        self.current_cashier = None
        self.join_time = None
        if urgency == 'Fast':
            self.max_wait = 120  # seconds
            self.check_interval = 30
        elif urgency == 'Normal':
            self.max_wait = 300
            self.check_interval = 60
        elif urgency == 'Calm':
            self.max_wait = 600
            self.check_interval = 120

class Cashier:
    def __init__(self, id, min_time, max_time):
        self.id = id
        self.min_time = min_time
        self.max_time = max_time
        self.avg_time = (min_time + max_time) / 2
        self.queue = []  # list of Customers waiting
        self.current_customer = None
        self.service_end_time = 0
        self.busy = False
        self.total_busy_time = 0

def generate_customers(num_customers):
    customers = []
    for i in range(num_customers):
        type_ = random.choice(['Solo', 'Family'])
        if type_ == 'Solo':
            basket = random.randint(1, 15)
        else:
            basket = random.randint(10, 50)
        urgency = random.choice(['Fast', 'Normal', 'Calm'])
        customers.append(Customer(i, type_, basket, urgency))
    return customers

def schedule_arrivals(customers, mean_interarrival):
    time = 0
    for cust in customers:
        inter = random.expovariate(1 / mean_interarrival)
        time += inter
        cust.arrival_time = time
    return time

def estimated_start_time(cashier, current_time):
    time = max(current_time, cashier.service_end_time) if cashier.busy else current_time
    for cust in cashier.queue:
        time += cust.basket_size * cashier.avg_time
    return time

def choose_cashier(customer, current_time, cashiers):
    min_total = float('inf')
    best_cashier = None
    for cashier in cashiers:
        start = estimated_start_time(cashier, current_time)
        wait = start - current_time
        service = customer.basket_size * cashier.avg_time
        total = wait + service
        if total < min_total:
            min_total = total
            best_cashier = cashier
    return best_cashier

def actual_service_time(cashier, customer):
    time = 0
    for _ in range(customer.basket_size):
        item_time = random.uniform(cashier.min_time, cashier.max_time)
        # Add probability to take longer: with 20% chance, add extra 50% time
        if random.random() < 0.2:
            item_time *= 1.5
        time += item_time
    return time

def process_arrival(current_time, customer, event_queue, cashiers):
    global priority_counter
    cashier = choose_cashier(customer, current_time, cashiers)
    customer.current_cashier = cashier
    customer.join_time = current_time
    if not cashier.busy and not cashier.queue:
        customer.start_service_time = current_time
        service_time = actual_service_time(cashier, customer)
        cashier.busy = True
        cashier.current_customer = customer
        cashier.service_end_time = current_time + service_time
        cashier.total_busy_time += service_time
        customer.departure_time = cashier.service_end_time
        heapq.heappush(event_queue, (cashier.service_end_time, priority_counter, 'end_service', cashier))
        priority_counter += 1
    else:
        cashier.queue.append(customer)
    # Schedule check
    check_time = current_time + customer.check_interval
    heapq.heappush(event_queue, (check_time, priority_counter, 'check_behavior', customer))
    priority_counter += 1

def process_end_service(current_time, cashier, event_queue):
    global priority_counter
    cust = cashier.current_customer
    cust.departure_time = current_time
    cashier.busy = False
    cashier.current_customer = None
    if cashier.queue:
        next_cust = cashier.queue.pop(0)
        next_cust.start_service_time = current_time
        service_time = actual_service_time(cashier, next_cust)
        cashier.busy = True
        cashier.current_customer = next_cust
        cashier.service_end_time = current_time + service_time
        cashier.total_busy_time += service_time
        next_cust.departure_time = cashier.service_end_time
        heapq.heappush(event_queue, (cashier.service_end_time, priority_counter, 'end_service', cashier))
        priority_counter += 1

def process_check_behavior(current_time, customer, event_queue, cashiers):
    global priority_counter
    if customer.abandoned or customer.start_service_time is not None:
        return
    # Check abandon
    est_start = estimated_start_time(customer.current_cashier, current_time)
    wait_from_now = est_start - current_time
    total_wait = (current_time - customer.arrival_time) + wait_from_now
    if total_wait > customer.max_wait:
        customer.abandoned = True
        customer.current_cashier.queue = [c for c in customer.current_cashier.queue if c.id != customer.id]
        return
    # Check switch
    current_cashier = customer.current_cashier
    current_est_start = estimated_start_time(current_cashier, current_time)
    current_wait = current_est_start - current_time
    current_service = customer.basket_size * current_cashier.avg_time
    current_total = current_wait + current_service
    best_cashier = choose_cashier(customer, current_time, cashiers)
    best_est_start = estimated_start_time(best_cashier, current_time)
    best_wait = best_est_start - current_time
    best_service = customer.basket_size * best_cashier.avg_time
    best_total = best_wait + best_service
    if best_total < current_total * 0.8:
        # switch
        current_cashier.queue = [c for c in current_cashier.queue if c.id != customer.id]
        customer.current_cashier = best_cashier
        if not best_cashier.busy and not best_cashier.queue:
            customer.start_service_time = current_time
            service_time = actual_service_time(best_cashier, customer)
            best_cashier.busy = True
            best_cashier.current_customer = customer
            best_cashier.service_end_time = current_time + service_time
            best_cashier.total_busy_time += service_time
            customer.departure_time = best_cashier.service_end_time
            heapq.heappush(event_queue, (best_cashier.service_end_time, priority_counter, 'end_service', best_cashier))
            priority_counter += 1
        else:
            best_cashier.queue.append(customer)
    # Next check
    next_check = current_time + customer.check_interval
    heapq.heappush(event_queue, (next_check, priority_counter, 'check_behavior', customer))
    priority_counter += 1

def run_simulation():
    global priority_counter
    priority_counter = 0
    event_queue = []
    cashiers = [
        Cashier(1, 1.5, 3.0),
        Cashier(2, 1.0, 2.0),
        Cashier(3, 2.0, 4.0),
        Cashier(4, 0.5, 1.5),
    ]
    num_customers = 100
    mean_interarrival = 30.0
    customers = generate_customers(num_customers)
    schedule_arrivals(customers, mean_interarrival)
    for cust in customers:
        heapq.heappush(event_queue, (cust.arrival_time, priority_counter, 'arrival', cust))
        priority_counter += 1
    current_time = 0
    while event_queue:
        time, pri, etype, obj = heapq.heappop(event_queue)
        if time > current_time:
            current_time = time
        if etype == 'arrival':
            process_arrival(current_time, obj, event_queue, cashiers)
        elif etype == 'end_service':
            process_end_service(current_time, obj, event_queue)
        elif etype == 'check_behavior':
            process_check_behavior(current_time, obj, event_queue, cashiers)
    # Metrics
    total_wait = 0
    num_completed = 0
    num_abandoned = 0
    for cust in customers:
        if cust.abandoned:
            num_abandoned += 1
        elif cust.start_service_time is not None:
            wait = cust.start_service_time - cust.arrival_time
            total_wait += wait
            num_completed += 1
    avg_wait = total_wait / num_completed if num_completed > 0 else 0
    abandon_rate = num_abandoned / num_customers if num_customers > 0 else 0
    total_time = current_time
    utilizations = [c.total_busy_time / total_time if total_time > 0 else 0 for c in cashiers]
    avg_util = sum(utilizations) / len(cashiers) if cashiers else 0
    print(f"Average waiting time: {avg_wait:.2f} seconds")
    print(f"Average cashier utilization: {avg_util:.2f}")
    print(f"Abandonment rate: {abandon_rate:.2f}")
    for i, u in enumerate(utilizations):
        print(f"Cashier {i+1} utilization: {u:.2f}")

if __name__ == "__main__":
    run_simulation()