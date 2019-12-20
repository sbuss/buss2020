import csv
from datetime import datetime
from decimal import Decimal
import getpass
import re
import time

from selenium.webdriver.common.keys import Keys


def login(driver):
    driver.get("https://netfile.com/Filer/Authentication/LogIn")

    driver.find_element_by_id("UserName")
    elem = driver.find_element_by_id("UserName")
    elem.send_keys("steven.buss@gmail.com")
    elem = driver.find_element_by_id("Password")
    pw = getpass.getpass("password: ")
    elem.send_keys(pw)
    elem.send_keys(Keys.RETURN)


def create_all_individuals(driver, contributions):
    """Create all individuals in ActBlue contributions.

    WARNING: This will not correctly handle people with the same
    {first,last}-name.
    """
    with open(contributions, 'r') as f:
        reader = csv.DictReader(f)
        names = set()
        for row in reader:
            name = row['Donor First Name'] + ' ' + row['Donor Last Name']
            if name in names:
                print("Already seen %s; skipping" % name)
                continue
            if entity_exists(driver, name):
                print("%s exists; skipping" % name)
                names.add(name)
                continue
            create_individual(driver, row)
            print("Created %s" % name)
            names.add(name)


def get_entity_for_contribution(driver, name):
    driver.get("https://netfile.com/Filer/LegacyFree/Entity/SelectEntity?TT=MonetaryContribution")  # NOQA
    elem = driver.find_element_by_id("EntityName")
    elem.send_keys(name)
    elem.send_keys(Keys.RETURN)


def entity_exists(driver, name):
    get_entity_for_contribution(driver, name)
    elem = driver.find_element_by_id("SearchResults")
    if not elem:
        return False
    for ee in elem.find_elements_by_tag_name("td"):
        if ee.text == name:
            return True
    return False


def create_individual(driver, person):
    driver.get("https://netfile.com/Filer/LegacyFree/Entity/PeopleAdd?InProgressTransactionType=MonetaryContribution")  # NOQA

    actblue_to_netfile = [
        ('Donor First Name', 'FirstName_modal'),
        ('Donor Last Name', 'LastName_modal'),
        ('Donor City', 'BusinessAddress_City'),
        ('Donor State', 'BusinessAddress_State'),
        ('Donor ZIP', 'BusinessAddress_ZipCode'),
        ('Donor Employer', 'Employer_modal'),
        ('Donor Occupation', 'Occupation_modal'),
        ('Donor Email', 'Email_modal'),
    ]
    for (person_col, elem_name) in actblue_to_netfile:
        elem = driver.find_element_by_id(elem_name)
        elem.send_keys(person[person_col])

    # Address and phone are special case, because:
    #  - Apt number is in BusinessAddress_Line2
    #  - Phone is split across three fields
    addr1, addr2 = person['Donor Addr1'], ""
    pattern = re.compile(
        r'(?P<addr1>.+)\s+(Apartment|Apt\.?|\#|Unit)\s?(?P<unit>.+)?',
        re.IGNORECASE)

    m = pattern.match(person['Donor Addr1'])
    if m:
        addr1 = m.groupdict()['addr1']
        addr2 = m.groupdict()['unit']
    else:
        addr1 = person['Donor Addr1']
    elem = driver.find_element_by_id('BusinessAddress_Line1')
    elem.send_keys(addr1)
    if addr2:
        elem = driver.find_element_by_id('BusinessAddress_Line2')
        elem.send_keys("Apt " + addr2)

    if person['Donor Country'] == "United States":
        phone = person['Donor Phone'].strip()
        phone = re.sub(r'[^\d]', '', person['Donor Phone'])
        if phone:
            pattern = re.compile(
                r'1?(?P<area>\d{3})(?P<exchange>\d{3})(?P<number>\d{4})')
            m = pattern.match(phone)
            if m:
                elem = driver.find_element_by_id('WorkPhone_AreaCode')
                elem.send_keys(m.groupdict()['area'])
                elem = driver.find_element_by_id('WorkPhone_Exchange')
                elem.send_keys(m.groupdict()['exchange'])
                elem = driver.find_element_by_id('WorkPhone_Number')
                elem.send_keys(m.groupdict()['number'])
    elem.send_keys(Keys.RETURN)


def create_all_contributions(driver, contributions):
    with open(contributions, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            create_contribution(driver, row)


def create_contribution(driver, contribution):
    """ONLY RUN THIS ONCE per line."""
    name = "%s %s" % (
        contribution['Donor First Name'], contribution['Donor Last Name'])
    print(name)
    get_entity_for_contribution(driver, name)
    elem = driver.find_element_by_id("SearchResults")
    if not elem:
        print("Entity doesn't exist: %s" % name)
        return
    clicked = False
    for ee in elem.find_elements_by_tag_name("td"):
        if ee.text == name:
            ee.parent.find_elements_by_tag_name(
                'td')[0].find_element_by_tag_name('a').click()
            clicked = True
            break
    if not clicked:
        print("Couldn't find matching element for %s" % name)
        return

    time.sleep(1)  # Sleep 2 seconds so the page loads
    contribution_date = datetime.strptime(
        contribution['Date'], '%Y-%m-%d %H:%M:%S')
    elem = driver.find_element_by_id('Date')
    elem.send_keys(contribution_date.strftime("%m/%d/%Y"))

    contribution_amount = Decimal(contribution['Amount'])
    elem = driver.find_element_by_id('Amount')
    elem.send_keys("{:.2f}".format(contribution_amount))

    elem = driver.find_element_by_id('ElectionCycle-input')
    elem.send_keys("Primary")
    elem.send_keys(Keys.RETURN)
