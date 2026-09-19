async (page) => {
  // Run through the Playwright browser_run_code tool against a fresh test app.
  const failures = [];
  const check = (condition, message) => { if (!condition) failures.push(message); };
  await page.reload();
  await page.waitForFunction(() => document.querySelector('#connection').textContent === 'Connected to your desktop');
  await page.locator('#title').fill('A small reminder');
  await page.locator('#body').fill('Take a breath.\nMake room for the next idea.');
  await page.getByRole('button', { name: 'Mint', exact: true }).click();
  await page.locator('#save').click();
  await page.waitForSelector('.note-card');
  check(await page.locator('.note-card').count() === 1, 'create card');
  check(await page.locator('.note-card').evaluate(el => getComputedStyle(el).backgroundColor) === 'rgb(204, 235, 217)', 'mint background');
  await page.locator('#body').fill('Unsaved draft stays here');
  await page.waitForTimeout(2200);
  check(await page.locator('#body').inputValue() === 'Unsaved draft stays here', 'poll preserves draft');
  await page.locator('#save').click();
  await page.waitForFunction(() => document.querySelector('.note-text').textContent === 'Unsaved draft stays here');
  await page.locator('.card-actions').getByRole('button', {name:'Hide', exact:true}).click();
  await page.waitForFunction(() => document.querySelector('.note-meta').textContent === 'Hidden from desktop');
  await page.locator('.card-actions').getByRole('button', {name:'Show', exact:true}).click();
  await page.waitForFunction(() => document.querySelector('.note-meta').textContent === 'On your desktop');
  await page.locator('#reminder-mode').selectOption('set');
  await page.locator('#minutes').fill('0.05');
  await page.locator('#save').click();
  await page.waitForFunction(() => !document.querySelector('#save').disabled);
  await page.locator('.card-actions').getByRole('button', {name:'Hide', exact:true}).click();
  await page.waitForSelector('.note-card.alert', {timeout:10000});
  check(await page.locator('.card-actions').getByRole('button', {name:'Hide', exact:true}).count() === 1, 'timer reveals note');
  await page.locator('.card-actions').getByRole('button', {name:'Dismiss', exact:true}).click();
  await page.waitForFunction(() => !document.querySelector('.note-card.alert'));
  await page.setViewportSize({width:390,height:844});
  check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'mobile overflow');
  await page.setViewportSize({width:1280,height:900});
  check(await page.locator('#error').isHidden(), 'no error banner');
  if(failures.length) throw Error(failures.join(', '));
  return {passed: ['create', 'edit', 'color', 'polling draft', 'hide/show', 'hidden timer reveal', 'dismiss', 'mobile layout']};
}
