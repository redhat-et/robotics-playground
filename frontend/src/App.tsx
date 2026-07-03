import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Page } from '@patternfly/react-core';
import RoboticsPlayground from './RoboticsPlayground';

const App: React.FC = () => (
  <BrowserRouter>
    <Page>
      <Routes>
        <Route path="/*" element={<RoboticsPlayground />} />
      </Routes>
    </Page>
  </BrowserRouter>
);

export default App;
