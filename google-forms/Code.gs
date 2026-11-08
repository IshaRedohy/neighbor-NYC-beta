/* NYC Neighbor Hub — paste into a standalone script at script.google.com.
 * Run setupForm once, then set Script Properties as described in docs/GOOGLE_FORMS.md.
 * No Google Sheet is created. Responses remain in Google Forms until you delete them.
 */
function props_() { return PropertiesService.getScriptProperties(); }

function setupForm() {
  var props = props_();
  if (props.getProperty('FORM_ID')) throw new Error('A form is already configured. Use its existing edit URL.');
  var form = FormApp.create('Neighbor NYC — Find your people');
  form.setDescription('An invitation-only community for New Yorkers aged 18+. Connect through shared skills, languages, and experiences. Profiles are reviewed by the community host. Shared backgrounds are not a guarantee of trust. Your Google account email is used privately for sign-in and approval by the host and is not shown to other members. ZIP code is required. Street address is optional, visible to you and the reviewing host, and hidden from other members. No phone number is required. Keep contact details out of free-text answers. Responses are stored in Google Forms and, after validation, a locally hosted database. You can hide or delete your app profile; ask the host to remove your original Google Form response. Existing message text remains under “Deleted member” after account deletion.');
  form.setCollectEmail(true);
  form.setAllowResponseEdits(false);
  form.setConfirmationMessage('Thanks for saying hello! Your community host will review your profile. Sign in using the same Google email once your host confirms approval.');
  var ids = {};
  function text(key, title, required, help) {
    var item = form.addTextItem().setTitle(title).setRequired(required);
    if (help) item.setHelpText(help);
    item.setValidation(FormApp.createTextValidation().requireTextLengthLessThanOrEqualTo(key === 'name' ? 80 : key === 'zip' ? 5 : key === 'address' ? 240 : ['occupation','workplace'].indexOf(key)>=0 ? 100 : 720).build());
    ids[key] = String(item.getId());
    return item;
  }
  text('name','Display name',true,'Use the name you want neighbors to see. A legal name or profile photo is not required.');
  text('zip','NYC residential ZIP code',true,'Five digits. Used for approximate nearby discovery; do not include your home address.')
    .setValidation(FormApp.createTextValidation().requireTextMatchesPattern('^[0-9]{5}$').build());
  text('address','Street address (optional)',false,'Private: visible to you and the reviewing host, not other members. Nearby matching uses your required ZIP code.');
  text('occupation','Your work or occupation',true,'Studying, caregiving, and looking for work count too.');
  text('workplace','Workplace',false,'Optional. Only include this if you want to share it with approved members.');
  text('languages','Languages you speak',true,'Separate entries with commas, for example: English, Bengali, Spanish. Up to 12.');
  text('expertise','Skills or experience you can help with',true,'Separate entries with commas, for example: career advice, web development, English practice.');
  text('interests','Fields you are interested in',false,'Separate entries with commas.');
  text('needs','What would you like help with?',false,'Separate entries with commas.');
  text('cultures','Cultural identity / ethnicity',false,'Optional and self-described. Separate entries with commas. Leaving this blank does not affect admission.');
  text('countries','Country or countries of origin',false,'Optional. Separate entries with commas.');
  var bio = form.addParagraphTextItem().setTitle('A little about you').setHelpText('Up to 800 characters. What would you like your neighbors to know?')
    .setValidation(FormApp.createParagraphTextValidation().requireTextLengthLessThanOrEqualTo(800).build());
  ids.bio = String(bio.getId());
  var adult = form.addCheckboxItem().setTitle('Age confirmation').setChoiceValues(['I am 18 or older']).setRequired(true);
  ids.adult = String(adult.getId());
  var consent = form.addCheckboxItem().setTitle('Community profile consent').setChoiceValues(['I agree to the storage and sharing described above, and to showing my public profile fields (excluding email and street address) to approved members.']).setRequired(true);
  ids.consent = String(consent.getId());
  props.setProperty('FORM_ID',form.getId());
  props.setProperty('QUESTION_IDS',JSON.stringify(ids));
  props.setProperty('RETRY_CURSOR','0');
  ScriptApp.newTrigger('onFormSubmit').forForm(form).onFormSubmit().create();
  ScriptApp.newTrigger('retryResponses').timeBased().everyMinutes(10).create();
  console.log('FORM_ID: '+form.getId());
  console.log('Edit: '+form.getEditUrl());
  console.log('Share: '+form.getPublishedUrl());
}

function payload_(response) {
  var ids=JSON.parse(props_().getProperty('QUESTION_IDS')), answers={};
  response.getItemResponses().forEach(function(item) { answers[String(item.getItem().getId())]=item.getResponse(); });
  function value(key) { return String(answers[ids[key]] || '').trim(); }
  function list(key) { return value(key).split(',').map(function(v){return v.trim();}).filter(Boolean); }
  function checked(key) { var result=answers[ids[key]]; return Array.isArray(result) && result.length === 1; }
  return {version:1,formId:props_().getProperty('FORM_ID'),responseId:response.getId(),
    email:response.getRespondentEmail(),adult:checked('adult'),consent:checked('consent'),
    profile:{name:value('name'),zip:value('zip'),address:value('address'),occupation:value('occupation'),workplace:value('workplace'),bio:value('bio'),
      languages:list('languages'),cultures:list('cultures'),countries:list('countries'),expertise:list('expertise'),interests:list('interests'),needs:list('needs')}};
}

function deliver_(response) {
  var props=props_(), endpoint=props.getProperty('INTAKE_URL'),secret=props.getProperty('INTAKE_SECRET');
  if (!endpoint || !secret) return false; // Collection and manual export work without a tunnel.
  if (!/^https:\/\//.test(endpoint) || secret.length<32) throw new Error('Use an HTTPS intake URL and a secret of at least 32 characters.');
  var body=JSON.stringify(payload_(response)),timestamp=String(Date.now());
  var bytes=Utilities.computeHmacSha256Signature(timestamp+'.'+body,secret,Utilities.Charset.UTF_8);
  var signature=bytes.map(function(b){return ('0'+((b+256)%256).toString(16)).slice(-2);}).join('');
  try {
    var res=UrlFetchApp.fetch(endpoint,{method:'post',contentType:'application/json',payload:body,muteHttpExceptions:true,
      followRedirects:false,headers:{'X-Intake-Timestamp':timestamp,'X-Intake-Signature':signature}});
    var status=res.getResponseCode();
    if(status>=200 && status<300) return true;
    // Avoid logging personal response contents. Validation problems can be reviewed through an import.
    console.warn('Delivery failed. Response '+response.getId()+', HTTP '+status+'. Export responses to review validation errors.');
  } catch (e) { console.warn('Delivery unavailable; scheduled recovery will retry.'); }
  return false;
}

function onFormSubmit(event) { deliver_(event.response); }

function retryResponses() {
  var lock=LockService.getScriptLock();
  if(!lock.tryLock(1000)) return;
  try {
    var props=props_();
    if(!props.getProperty('INTAKE_URL') || !props.getProperty('INTAKE_SECRET')) return;
    var responses=FormApp.openById(props.getProperty('FORM_ID')).getResponses();
    var cursor=Number(props.getProperty('RETRY_CURSOR')||0);
    if(cursor>=responses.length)cursor=0;
    // Rotate through all responses in bounded batches. Delivery is idempotent at the API.
    // This also recovers responses submitted while the laptop or tunnel was offline.
    for(var i=cursor;i<Math.min(cursor+25,responses.length);i++) {
      deliver_(responses[i]);
      props.setProperty('RETRY_CURSOR',String(i+1));
    }
  } finally { lock.releaseLock(); }
}

function exportResponses() {
  var responses=FormApp.openById(props_().getProperty('FORM_ID')).getResponses();
  for(var i=0;i<responses.length;i+=100) {
    var batch=responses.slice(i,i+100).map(payload_);
    var file=DriveApp.createFile('neighbor-responses-'+new Date().toISOString().slice(0,10)+'-'+(i/100+1)+'.json',JSON.stringify({submissions:batch},null,2),MimeType.PLAIN_TEXT);
    console.log('Private export: '+file.getUrl());
  }
  if(!responses.length)console.log('No responses yet.');
}
