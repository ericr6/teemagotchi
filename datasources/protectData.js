#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { IExecDataProtector, getWeb3Provider } = require('@iexec/dataprotector');
require('dotenv').config();

const PRIVATE_KEY = process.env.PRIVATE_KEY;
const AUTHORIZED_APP = process.env.AUTHORIZED_APP;

if (!PRIVATE_KEY || !AUTHORIZED_APP) {
  console.error('❌ PRIVATE_KEY or AUTHORIZED_APP not set in environment variables');
  process.exit(1);
}

const filePath = process.argv[2];
if (!filePath) {
  console.error('❌ No file path provided');
  process.exit(1);
}

(async () => {
  try {
    const web3Provider = getWeb3Provider(PRIVATE_KEY);
    const dataProtector = new IExecDataProtector(web3Provider);
    const dataProtectorCore = dataProtector.core;

    const fileBuffer = fs.readFileSync(filePath);

    // Protect the data
    const protectedData = await dataProtectorCore.protectData({
      name: path.basename(filePath),
      data: {
        file: fileBuffer,
      },
    });

    // Grant access to the specified iApp for all users
    await dataProtectorCore.grantAccess({
      protectedData: protectedData.address,
      authorizedApp: AUTHORIZED_APP,
      authorizedUser: '0x0000000000000000000000000000000000000000', // All users
    });

    console.log(protectedData.address);
  } catch (error) {
    console.error('❌ Error:', error.message);
    process.exit(1);
  }
})();
