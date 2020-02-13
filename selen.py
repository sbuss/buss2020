import argparse
import csv
from datetime import datetime
from decimal import Decimal
import getpass
import re
import time

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select


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

    try:
        elem = driver.find_element_by_link_text('Select an Intermediary')
    except NoSuchElementException:
        print("#### Couldn't enter intermediary for %s" % name)
    else:
        elem.click()
        time.sleep(1)
        elem = driver.find_element_by_id('EntityName')
        elem.send_keys('ActBlue')
        elem.send_keys(Keys.RETURN)
        time.sleep(1)
        links = driver.find_elements_by_link_text('Select')
        if len(links) > 1:
            print("Too many links for %s" % name)
        links[0].click()
        time.sleep(0.5)
        driver.find_element_by_name('btnSubmit').click()
        time.sleep(1)
    elem = driver.find_element_by_id('ElectionCycle-input')
    elem.send_keys(Keys.RETURN)


def create_all_fees(driver, contributions):
    """Create all fee disbursements in ActBlue contributions.

    ONLY RUN THIS ONCE per line."""
    actblue = 'ActBlue Techincal Services'
    if not entity_exists(driver, actblue):
        create_actblue_entity(driver, actblue)
    get_entity_for_disbursements(driver, actblue)
    elem = driver.find_element_by_id("SearchResults")
    if not elem:
        print("Entity doesn't exist: %s" % actblue)
        return
    clicked = False
    for ee in elem.find_elements_by_tag_name("td"):
        if ee.text == actblue:
            ee.parent.find_elements_by_tag_name(
                'td')[0].find_element_by_tag_name('a').click()
            clicked = True
            break
    if not clicked:
        print("Couldn't find matching element for %s" % actblue)
        return

    time.sleep(1)  # Sleep 1 second so the page loads

    with open(contributions, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            time.sleep(1)  # Sleep 1 second so the page loads
            fee_date = datetime.strptime(
                row['Date'], '%Y-%m-%d %H:%M:%S')
            elem = driver.find_element_by_id('Date')
            elem.send_keys(fee_date.strftime("%m/%d/%Y"))

            fee_amount = Decimal(row['Fee'])
            elem = driver.find_element_by_id('Amount')
            elem.send_keys("{:.2f}".format(fee_amount))

            elem = Select(
                driver.find_element_by_id('FppcSpendCodeDropDownField'))
            elem.select_by_value("OFC")

            elem = driver.find_element_by_id('DescriptionField')
            elem.send_keys('Service Fee')

            elem = driver.find_element_by_id('ElectionCycle-input')
            elem.send_keys('Primary')

            elem = driver.find_element_by_id('form-submit-button')
            elem.click()


def create_actblue_entity(driver, name):
    driver.get("https://netfile.com/Filer/LegacyFree/Entity/OrganizationAdd?InProgressTransactionType=Disbursements")  # NOQA

    actblue_to_netfile = [
        ('Name_modal', name),
        ('BusinessAddress_Line1', 'PO Box 441146'),
        ('BusinessAddress_City', 'Somerville'),
        ('BusinessAddress_State', 'MA'),
        ('BusinessAddress_ZipCode', '02144'),
    ]
    for (elem_name, val) in actblue_to_netfile:
        elem = driver.find_element_by_id(elem_name)
        elem.send_keys(val)
    elem.send_keys(Keys.RETURN)


def get_entity_for_disbursements(driver, name):
    driver.get("https://netfile.com/Filer/LegacyFree/Entity/SelectEntity?TT=Disbursements")  # NOQA
    elem = driver.find_element_by_id("EntityName")
    elem.send_keys(name)
    elem.send_keys(Keys.RETURN)


def _add_intermediaries(driver):
    driver.get("https://netfile.com/Filer/LegacyFree/Transaction")
    time.sleep(0.5)
    all_hrefs = []
    while True:
        time.sleep(0.5)
        elems = driver.find_elements_by_tag_name("tr")
        print("Found %d elems" % len(elems))
        for ee in elems:
            eet = ee.text
            if 'Monetary Contribution' in eet:
                href = ee.find_element_by_link_text('Edit').get_attribute('href')
                print('adding %s' % href)
                all_hrefs.append(href)
        elem = driver.find_element_by_link_text('next')
        if 't-state-disabled' in elem.get_attribute('class'):
            break
        else:
            elem.click()
    print("Found %d links" % len(all_hrefs))
    for c, href in enumerate(all_hrefs):
        print("Link #%d: %s" % (c, href))
        driver.get(href)
        time.sleep(0.5)
        try:
            elem = driver.find_element_by_link_text('Enter an Intermediary')
        except NoSuchElementException:
            continue
        elem.click()
        time.sleep(0.5)
        elem = driver.find_element_by_id('EntityName')
        elem.send_keys('ActBlue')
        elem.send_keys(Keys.RETURN)
        time.sleep(0.5)
        links = driver.find_elements_by_link_text('Select')
        if len(links) > 1:
            print("Too many links for href %s" % href)
            continue
        links[0].click()
        time.sleep(0.5)
        driver.find_element_by_name('btnSubmit').click()
        time.sleep(0.5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import ActBlue contributions into Netfile")
    parser.add_argument(
        'contributions_file', help='Path to your contributions files')
    parser.add_argument(
        '--method', help='Import individuals or their donations?',
        choices=[
            'people',  # Donors
            'donations',  # Individual donations
            'fees',  # Fees for donations (counts as disbursement)
        ])
    args = parser.parse_args()

    driver = webdriver.Chrome()
    login(driver)
    if args.method == 'people':
        create_all_individuals(driver, args.contributions_file)
    elif args.method == 'donations':
        create_all_contributions(driver, args.contributions_file)
    elif args.method == 'fees':
        create_all_fees(driver, args.contributions_file)
