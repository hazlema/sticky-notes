async (page) => {
  await page.reload();
  await page.waitForFunction(() => document.querySelector('#connection').textContent === 'Connected to your desktop');
  const controls = await page.evaluate(() => ({
    hours: document.querySelector('#hours')?.tagName,
    minutes: document.querySelector('#minutes')?.tagName
  }));
  if (controls.hours !== 'SELECT' || controls.minutes !== 'SELECT') throw Error('Hours and minutes must both be dropdowns');
  const options = await page.evaluate(() => ({
    hours: [...document.querySelector('#hours').options].map(o => Number(o.value)),
    minutes: [...document.querySelector('#minutes').options].map(o => Number(o.value)),
    defaults: [document.querySelector('#hours').value, document.querySelector('#minutes').value]
  }));
  if (JSON.stringify(options.hours) !== JSON.stringify(Array.from({length:25}, (_,i)=>i))) throw Error('Hours must range from 0 through 24');
  if (JSON.stringify(options.minutes) !== JSON.stringify(Array.from({length:61}, (_,i)=>i))) throw Error('Minutes must range from 0 through 60');
  if (options.defaults.join(',') !== '0,0') throw Error('Defaults must be zero');
  await page.locator('#title').fill('Timer dropdown test');
  await page.locator('#reminder-mode').selectOption('set');
  await page.locator('#save').click();
  if (!(await page.locator('#error').textContent()).includes('at least 1 minute')) throw Error('Zero duration must be explained');
  await page.locator('#hours').selectOption('1');
  await page.locator('#minutes').selectOption('30');
  await page.locator('#save').click();
  await page.waitForFunction(() => document.querySelector('#draft-state').textContent === 'Saved on your computer');
  const read = () => page.evaluate(async () => (await fetch('/api/notes', {headers:{Authorization:'Bearer '+sessionStorage.getItem('sticky-token')}})).json());
  let note = (await read()).find(n => n.title === 'Timer dropdown test');
  if (Math.abs(note.deadline - Date.now()/1000 - 5400) > 10) throw Error('1 hour 30 minutes must schedule 90 minutes');
  await page.locator('#reminder-mode').selectOption('set');
  await page.locator('#hours').selectOption('24');
  await page.locator('#minutes').selectOption('60');
  await page.locator('#save').click();
  await page.waitForFunction(() => !document.querySelector('#save').disabled);
  note = (await read()).find(n => n.title === 'Timer dropdown test');
  if (Math.abs(note.deadline - Date.now()/1000 - 90000) > 10) throw Error('24 hours + 60 minutes must be accepted');
  await page.setViewportSize({width:390,height:844});
  if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw Error('Mobile overflow');
  await page.setViewportSize({width:1280,height:900});
  return {passed:['dropdown ranges', 'zero defaults', 'zero duration validation', '90-minute timer', 'maximum duration', 'mobile layout']};
}
